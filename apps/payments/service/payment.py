from __future__ import annotations

import contextlib
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.orders.enums import OrderStatusEnum
from apps.orders.service.order import OrderService
from apps.payments.enums import PaymentStatusEnum
from apps.payments.models import Payment
from apps.payments.models import PaymentStatusHistory
from core.exceptions import InvalidStatusTransitionError

if TYPE_CHECKING:
    from decimal import Decimal
    from typing import Any

    from apps.orders.models import Order
    from apps.payments.models import PaymentMethod
    from apps.pricing.models import Currency
    from apps.staff.models import StaffProfile


# Allowed transitions


_PAYMENT_TRANSITIONS: dict[str, set[str]] = {
    PaymentStatusEnum.PENDING: {
        PaymentStatusEnum.PROCESSING,
        PaymentStatusEnum.CANCELLED,
        PaymentStatusEnum.FAILED,
    },
    PaymentStatusEnum.PROCESSING: {
        PaymentStatusEnum.PAID,
        PaymentStatusEnum.REQUIRES_ACTION,
        PaymentStatusEnum.FAILED,
        PaymentStatusEnum.CANCELLED,
    },
    PaymentStatusEnum.REQUIRES_ACTION: {
        PaymentStatusEnum.PROCESSING,
        PaymentStatusEnum.FAILED,
        PaymentStatusEnum.CANCELLED,
    },
    PaymentStatusEnum.PAID: {
        PaymentStatusEnum.PARTIALLY_REFUNDED,
        PaymentStatusEnum.REFUNDED,
    },
    PaymentStatusEnum.PARTIALLY_REFUNDED: {PaymentStatusEnum.REFUNDED},
    PaymentStatusEnum.UNPAID: {PaymentStatusEnum.PENDING},
    PaymentStatusEnum.FAILED: set(),
    PaymentStatusEnum.CANCELLED: set(),
    PaymentStatusEnum.REFUNDED: set(),
}


# Input containers


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentInitInput:
    """All data required to initiate a payment."""

    order: Order
    gateway: str
    transaction_id: str
    amount: Decimal
    currency: Currency
    payment_method: PaymentMethod | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class PaymentTransitionMeta:
    """Optional context recorded alongside a payment status change."""

    changed_by: StaffProfile | None = None
    gateway_event: str = ""
    note: str = ""
    raw_response: dict[str, Any] | None = None


class PaymentService:
    # Create

    @classmethod
    @transaction.atomic
    def initiate(cls, *, data: PaymentInitInput) -> Payment:
        payment = Payment(
            order=data.order,
            gateway=data.gateway,
            transaction_id=data.transaction_id,
            amount=data.amount,
            currency=data.currency,
            payment_method=data.payment_method,
            raw_response=data.raw_response,
            status=PaymentStatusEnum.PENDING,
        )
        payment.full_clean()
        payment.save()

        # Initial history row.
        PaymentStatusHistory.objects.create(
            payment=payment,
            old_status="",
            new_status=PaymentStatusEnum.PENDING,
        )

        return payment

    # Status transitions

    @classmethod
    @transaction.atomic
    def transition_status(
        cls,
        payment: Payment,
        new_status: str,
        *,
        meta: PaymentTransitionMeta | None = None,
    ) -> Payment:
        meta = meta or PaymentTransitionMeta()

        allowed = _PAYMENT_TRANSITIONS.get(payment.status, set())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                entity="Payment",
                from_status=payment.status,
                to_status=new_status,
            )

        old_status = payment.status
        payment.status = new_status

        update_fields = ["status", "modified"]

        if meta.raw_response is not None:
            payment.raw_response = meta.raw_response
            update_fields.append("raw_response")

        if new_status in Payment.TERMINAL_STATUSES and payment.completed_at is None:
            payment.completed_at = timezone.now()
            update_fields.append("completed_at")

        payment.save(update_fields=update_fields)

        PaymentStatusHistory.objects.create(
            payment=payment,
            old_status=old_status,
            new_status=new_status,
            changed_by=meta.changed_by,
            gateway_event=meta.gateway_event,
            note=meta.note,
        )

        # Sync the denormalised payment_status on the Order.
        cls._sync_order_payment_status(payment, new_status)

        if new_status == PaymentStatusEnum.PAID:
            cls._maybe_confirm_order(payment)

        return payment

    # Gateway webhook handler

    @classmethod
    @transaction.atomic
    def handle_webhook(
        cls,
        *,
        transaction_id: str,
        new_status: str,
        gateway_event: str = "",
        raw_response: dict[str, Any] | None = None,
    ) -> Payment | None:
        try:
            payment = Payment.objects.select_related("order", "currency").get(
                transaction_id=transaction_id
            )
        except Payment.DoesNotExist:
            return None

        if payment.status == new_status:
            # Already in target state - idempotent no-op.
            return payment

        try:
            return cls.transition_status(
                payment,
                new_status,
                meta=PaymentTransitionMeta(
                    gateway_event=gateway_event,
                    raw_response=raw_response,
                ),
            )
        except InvalidStatusTransitionError:
            # Webhook arrived out of order (e.g. duplicate delivery). Ignore.
            return payment

    # Internal helpers

    @classmethod
    def _sync_order_payment_status(
        cls, payment: Payment, new_payment_status: str
    ) -> None:
        """Keep Order.payment_status in sync with the latest payment status."""

        # Non-fatal - Order sync is best-effort.
        with contextlib.suppress(Exception):
            OrderService.update_payment_status(payment.order, new_payment_status)

    @classmethod
    def _maybe_confirm_order(cls, payment: Payment) -> None:
        """Advance the order to CONFIRMED once its payment has been PAID.

        Non-fatal and a no-op if the order isn't PENDING (e.g. it was already
        confirmed by an earlier payment attempt, or already cancelled).
        """
        with contextlib.suppress(InvalidStatusTransitionError):
            OrderService.transition(payment.order, OrderStatusEnum.CONFIRMED)
