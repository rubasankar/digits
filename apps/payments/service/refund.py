from __future__ import annotations

import contextlib
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from apps.payments.enums import PaymentStatusEnum
from apps.payments.enums import RefundStatusEnum
from apps.payments.models import Payment
from apps.payments.models import Refund
from apps.payments.models import RefundItem
from apps.payments.models import RefundReason
from core.exceptions import InvalidStatusTransitionError
from core.exceptions import PaymentAlreadyRefundedError
from core.exceptions import RefundExceedsPaymentError

from .payment import PaymentService
from .payment import PaymentTransitionMeta

if TYPE_CHECKING:
    from apps.orders.models import OrderItem
    from apps.staff.models import StaffProfile


# Allowed transitions


_REFUND_TRANSITIONS: dict[str, set[str]] = {
    RefundStatusEnum.PENDING: {RefundStatusEnum.PROCESSING, RefundStatusEnum.FAILED},
    RefundStatusEnum.PROCESSING: {RefundStatusEnum.REFUNDED, RefundStatusEnum.FAILED},
    RefundStatusEnum.REFUNDED: set(),
    RefundStatusEnum.FAILED: set(),
}


# Input containers


@dataclass(slots=True, kw_only=True)
class RefundLineInput:
    order_item: OrderItem
    quantity: int
    amount: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class RefundMeta:
    """Optional context recorded when creating a refund."""

    reason: RefundReason | None = None
    lines: list[RefundLineInput] = field(default_factory=list)
    notes: str = ""
    refunded_by: StaffProfile | None = None


# RefundService


class RefundService:
    # Create

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        payment: Payment,
        amount: Decimal,
        meta: RefundMeta | None = None,
    ) -> Refund:
        meta = meta or RefundMeta()

        #  Guard: payment must be in a refundable state
        refundable = {PaymentStatusEnum.PAID, PaymentStatusEnum.PARTIALLY_REFUNDED}
        if payment.status not in refundable:
            raise InvalidStatusTransitionError(
                entity="Payment",
                from_status=payment.status,
                to_status="REFUND",
                message=str(
                    _(
                        "Refunds can only be issued for PAID "
                        "or PARTIALLY_REFUNDED payments."
                    )
                ),
            )

        if payment.status == PaymentStatusEnum.REFUNDED:
            raise PaymentAlreadyRefundedError

        #  Validate amount
        if amount <= Decimal("0"):
            raise ValidationError(
                {"amount": _("Refund amount must be greater than zero.")}
            )

        if amount > payment.amount:
            raise RefundExceedsPaymentError(
                refund_amount=amount,
                payment_amount=payment.amount,
            )

        #  Cumulative ceiling check
        already_refunded = cls._total_refunded(payment)
        if already_refunded + amount > payment.amount:
            raise RefundExceedsPaymentError(
                refund_amount=already_refunded + amount,
                payment_amount=payment.amount,
                message=_(
                    "Total refunded (%(total)s) would exceed "
                    "payment amount (%(payment)s)."
                )
                % {"total": already_refunded + amount, "payment": payment.amount},
            )

        #  Create Refund
        refund = Refund(
            payment=payment,
            amount=amount,
            reason=meta.reason,
            notes=meta.notes,
            status=RefundStatusEnum.PENDING,
            refunded_by=meta.refunded_by,
        )
        refund.full_clean()
        refund.save()

        #  Create RefundItems
        if meta.lines:
            for line in meta.lines:
                RefundItem.objects.create(
                    refund=refund,
                    order_item=line.order_item,
                    quantity=line.quantity,
                    amount=line.amount,
                )

        return refund

    # Process (gateway call result)

    @classmethod
    @transaction.atomic
    def process(
        cls,
        refund: Refund,
        *,
        transaction_id: str = "",
        changed_by: StaffProfile | None = None,
    ) -> Refund:
        return cls._transition(
            refund,
            RefundStatusEnum.PROCESSING,
            transaction_id=transaction_id,
            changed_by=changed_by,
        )

    @classmethod
    @transaction.atomic
    def confirm(
        cls,
        refund: Refund,
        *,
        transaction_id: str = "",
        changed_by: StaffProfile | None = None,
    ) -> Refund:
        # Allow direct PENDING -> REFUNDED (instant gateway response) or
        # PROCESSING -> REFUNDED (async confirmation).
        if refund.status == RefundStatusEnum.PENDING:
            refund = cls._transition(
                refund,
                RefundStatusEnum.PROCESSING,
                transaction_id=transaction_id,
                changed_by=changed_by,
            )
        return cls._transition(
            refund,
            RefundStatusEnum.REFUNDED,
            transaction_id=transaction_id,
            changed_by=changed_by,
        )

    @classmethod
    @transaction.atomic
    def fail(
        cls,
        refund: Refund,
        *,
        changed_by: StaffProfile | None = None,
        note: str = "",
    ) -> Refund:
        """Mark the refund as failed (gateway rejected it)."""
        return cls._transition(refund, RefundStatusEnum.FAILED, changed_by=changed_by)

    # Internal helpers

    @classmethod
    def _transition(
        cls,
        refund: Refund,
        new_status: str,
        *,
        transaction_id: str = "",
        changed_by: StaffProfile | None = None,
    ) -> Refund:
        allowed = _REFUND_TRANSITIONS.get(refund.status, set())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                entity="Refund",
                from_status=refund.status,
                to_status=new_status,
            )

        refund.status = new_status
        update_fields = ["status", "modified"]

        if transaction_id:
            refund.transaction_id = transaction_id
            update_fields.append("transaction_id")

        refund.save(update_fields=update_fields)

        # When a refund is confirmed, update the Payment status.
        if new_status == RefundStatusEnum.REFUNDED:
            cls._update_payment_after_refund(refund.payment)

        return refund

    @classmethod
    def _total_refunded(cls, payment: Payment) -> Decimal:
        """Sum of all non-FAILED refund amounts for this payment."""
        result = payment.refunds.exclude(status=RefundStatusEnum.FAILED).aggregate(
            total=Sum("amount")
        )["total"]
        return result or Decimal("0.00")

    @classmethod
    def _update_payment_after_refund(cls, payment: Payment) -> None:
        """
        Roll the Payment's aggregate status up from its confirmed Refunds.

        apps/payments is a ledger, not a payment engine: it doesn't decide
        gateway-side outcomes. This rollup is safe within that boundary only
        because every Refund summed here was itself already gateway-confirmed
        by RefundService.confirm() (called with the gateway's own call
        result) -- this just aggregates those confirmed records into the
        Payment-level field. If the gateway ever reports a payment-level
        refund status directly (e.g. a webhook carrying the charge's own
        `amount_refunded`), that should be applied via
        PaymentService.handle_webhook() instead, which takes priority since
        it comes straight from the gateway rather than a local sum.

        - total_refunded >= payment.amount -> REFUNDED
        - total_refunded <  payment.amount -> PARTIALLY_REFUNDED
        """

        total_refunded = cls._total_refunded(payment)

        if total_refunded >= payment.amount:
            target_status = PaymentStatusEnum.REFUNDED
        else:
            target_status = PaymentStatusEnum.PARTIALLY_REFUNDED

        if payment.status != target_status:
            with contextlib.suppress(InvalidStatusTransitionError):
                PaymentService.transition_status(
                    payment,
                    target_status,
                    meta=PaymentTransitionMeta(
                        note="Auto-updated after refund confirmation.",
                    ),
                )
