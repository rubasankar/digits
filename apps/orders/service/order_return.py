from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.inventory.services import MovementMeta
from apps.inventory.services import StockMovementService
from apps.orders.enums import OrderStatusEnum
from apps.orders.enums import ReturnRequestStatusEnum
from apps.orders.models import Order
from apps.orders.models import OrderItem
from apps.orders.models import ReturnRequest
from apps.orders.models import ReturnRequestItem
from apps.orders.models import ReturnRequestStatusHistory
from apps.orders.models import ReturnShipment
from core.exceptions import InvalidStatusTransitionError
from core.exceptions import OrderNotEligibleForReturnError
from core.exceptions import PermissionDeniedError
from core.exceptions import ReturnAlreadyExistsError
from core.exceptions import ReturnQuantityExceededError

from .order import OrderService

if TYPE_CHECKING:
    from apps.customers.models import CustomerProfile
    from apps.delivery.models import Fulfilment
    from apps.inventory.models import Warehouse
    from apps.staff.models import StaffProfile


# Allowed transitions


_RETURN_TRANSITIONS: dict[str, set[str]] = {
    ReturnRequestStatusEnum.PENDING: {
        ReturnRequestStatusEnum.APPROVED,
        ReturnRequestStatusEnum.REJECTED,
        ReturnRequestStatusEnum.CANCELLED,
    },
    ReturnRequestStatusEnum.APPROVED: {ReturnRequestStatusEnum.RETURN_SHIPPED},
    ReturnRequestStatusEnum.RETURN_SHIPPED: {ReturnRequestStatusEnum.RECEIVED},
    ReturnRequestStatusEnum.RECEIVED: {ReturnRequestStatusEnum.COMPLETED},
    ReturnRequestStatusEnum.REJECTED: set(),
    ReturnRequestStatusEnum.COMPLETED: set(),
    ReturnRequestStatusEnum.CANCELLED: set(),
}

# Statuses that DON'T count against a unit's returnability: the return never
# actually happened (staff rejected it, or the customer cancelled their own
# request). Deliberately narrower than ReturnRequest.TERMINAL_STATUSES, which
# also includes COMPLETED -- a completed return did take the units back, so
# it must keep counting or the same units could be returned/refunded twice.
_NON_COUNTING_RETURN_STATUSES = frozenset(
    {ReturnRequestStatusEnum.REJECTED, ReturnRequestStatusEnum.CANCELLED}
)


# Input dataclass


@dataclass(slots=True, kw_only=True)
class ReturnLineInput:
    """One line item to be returned."""

    order_item: OrderItem
    quantity_requested: int
    condition_note: str = ""


# ReturnRequestService


class ReturnRequestService:
    # Create

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        order: Order,
        customer: CustomerProfile,
        reason: str,
        lines: list[ReturnLineInput],
        customer_note: str = "",
    ) -> ReturnRequest:

        #  Guard: order must belong to this customer
        if order.customer_id != customer.pk:
            raise OrderNotEligibleForReturnError(
                str(_("This order does not belong to you."))
            )

        #  Guard: order status
        eligible_statuses = {
            OrderStatusEnum.DELIVERED,
            OrderStatusEnum.RETURN_REQUESTED,
        }
        if order.status not in eligible_statuses:
            raise OrderNotEligibleForReturnError(
                _(
                    "Returns can only be requested for delivered orders "
                    "(current status: %(s)s)."
                )
                % {"s": order.get_status_display()}
            )

        #  Guard: no active non-terminal return request already open
        active_exists = (
            ReturnRequest.objects.filter(
                order=order,
            )
            .exclude(status__in=ReturnRequest.TERMINAL_STATUSES)
            .exists()
        )
        if active_exists:
            raise ReturnAlreadyExistsError

        if not lines:
            raise ValueError(_("At least one return line is required."))

        #  Guard: per-line quantity check
        cls._validate_return_quantities(order, lines)

        #  Create ReturnRequest
        return_request = ReturnRequest(
            order=order,
            requested_by=customer,
            reason=reason,
            customer_note=customer_note,
            status=ReturnRequestStatusEnum.PENDING,
        )
        return_request.full_clean()
        return_request.save()

        #  Create ReturnRequestItems
        for line in lines:
            item = ReturnRequestItem(
                return_request=return_request,
                order_item=line.order_item,
                quantity_requested=line.quantity_requested,
                condition_note=line.condition_note,
            )
            item.full_clean()
            item.save()

        #  Status history
        ReturnRequestStatusHistory.objects.create(
            return_request=return_request,
            old_status="",
            new_status=ReturnRequestStatusEnum.PENDING,
        )

        #  Transition order status
        if order.status == OrderStatusEnum.DELIVERED:
            OrderService.transition(order, OrderStatusEnum.RETURN_REQUESTED)

        return return_request

    # Approve / Reject / Cancel

    @classmethod
    @transaction.atomic
    def approve(
        cls,
        return_request: ReturnRequest,
        *,
        reviewed_by: StaffProfile,
        staff_note: str = "",
    ) -> ReturnRequest:
        """Staff approves the return request."""
        cls._transition(
            return_request,
            ReturnRequestStatusEnum.APPROVED,
            changed_by=reviewed_by,
            note=staff_note,
        )
        return_request.reviewed_by = reviewed_by
        return_request.staff_note = staff_note
        return_request.approved_at = timezone.now()
        return_request.save(
            update_fields=["reviewed_by", "staff_note", "approved_at", "modified"]
        )
        return return_request

    @classmethod
    @transaction.atomic
    def reject(
        cls,
        return_request: ReturnRequest,
        *,
        reviewed_by: StaffProfile,
        staff_note: str = "",
    ) -> ReturnRequest:
        """
        Staff rejects the return request.

        Restores Order.status -> DELIVERED when no other active return exists.
        """

        cls._transition(
            return_request,
            ReturnRequestStatusEnum.REJECTED,
            changed_by=reviewed_by,
            note=staff_note,
        )
        return_request.reviewed_by = reviewed_by
        return_request.staff_note = staff_note
        return_request.save(update_fields=["reviewed_by", "staff_note", "modified"])

        cls._maybe_restore_order_delivered(return_request.order)
        return return_request

    @classmethod
    @transaction.atomic
    def cancel(
        cls,
        return_request: ReturnRequest,
        *,
        cancelled_by: CustomerProfile,
    ) -> ReturnRequest:
        """Customer cancels their own return request (only allowed from PENDING)."""
        if return_request.requested_by_id != cancelled_by.pk:
            raise PermissionDeniedError(
                str(_("You can only cancel your own return requests."))
            )

        cls._transition(return_request, ReturnRequestStatusEnum.CANCELLED)
        cls._maybe_restore_order_delivered(return_request.order)
        return return_request

    # Mark shipped

    @classmethod
    @transaction.atomic
    def mark_shipped(
        cls,
        return_request: ReturnRequest,
        *,
        tracking_number: str = "",
        carrier: str = "",
        changed_by: CustomerProfile | None = None,
    ) -> ReturnRequest:
        """Customer records that they have dispatched the return parcel."""
        cls._transition(return_request, ReturnRequestStatusEnum.RETURN_SHIPPED)

        shipment, _ = ReturnShipment.objects.get_or_create(
            return_request=return_request,
        )
        shipment.tracking_number = tracking_number
        shipment.carrier = carrier
        shipment.shipped_at = timezone.now()
        shipment.save(update_fields=["tracking_number", "carrier", "shipped_at"])

        return return_request

    # Receive (warehouse confirms goods received)

    @classmethod
    @transaction.atomic
    def receive(
        cls,
        return_request: ReturnRequest,
        *,
        received_by: StaffProfile,
        received_quantities: dict[object, int],  # {ReturnRequestItem.pk: qty_received}
        condition_notes: dict[object, str] | None = None,
    ) -> ReturnRequest:
        items = list(
            return_request.items.select_related("order_item__variant__product").all()
        )
        cls._validate_received_quantities(items, received_quantities)

        cls._transition(
            return_request,
            ReturnRequestStatusEnum.RECEIVED,
            changed_by=received_by,
        )

        now = timezone.now()
        return_request.received_at = now
        return_request.save(update_fields=["received_at", "modified"])

        # Update each line with received quantities and restock.
        for item in items:
            qty_received = received_quantities.get(item.pk, 0)
            note_text = (condition_notes or {}).get(item.pk, "")

            item.quantity_received = qty_received
            if note_text:
                item.condition_note = note_text
            item.save(update_fields=["quantity_received", "condition_note"])

            if qty_received > 0:
                # Find the warehouse from the original fulfilment. Skip when
                # the variant was deleted or no fulfilment exists.
                variant = item.order_item.variant
                warehouse = cls._get_fulfilment_warehouse(item.order_item)
                if variant is not None and warehouse is not None:
                    StockMovementService.restock_return(
                        variant=variant,
                        warehouse=warehouse,
                        quantity=qty_received,
                        meta=MovementMeta(
                            reference=f"RMA-{return_request.pk}",
                            note=f"Customer return - {item.order_item.variant_sku}",
                            performed_by=received_by,
                        ),
                    )

        # Stamp the ReturnShipment.
        try:
            shipment = return_request.shipment
            shipment.received_at = now
            shipment.received_by = received_by
            shipment.save(update_fields=["received_at", "received_by"])
        except ReturnShipment.DoesNotExist:
            pass

        return return_request

    # Complete

    @classmethod
    @transaction.atomic
    def complete(
        cls,
        return_request: ReturnRequest,
        *,
        changed_by: StaffProfile | None = None,
    ) -> ReturnRequest:

        cls._transition(
            return_request,
            ReturnRequestStatusEnum.COMPLETED,
            changed_by=changed_by,
        )
        return_request.completed_at = timezone.now()
        return_request.save(update_fields=["completed_at", "modified"])

        # Transition Order to RETURNED if all return requests are terminal.
        cls._maybe_mark_order_returned(return_request.order, changed_by=changed_by)

        return return_request

    # Internal helpers

    @classmethod
    def _transition(
        cls,
        return_request: ReturnRequest,
        new_status: str,
        *,
        changed_by: StaffProfile | None = None,
        note: str = "",
    ) -> None:
        allowed = _RETURN_TRANSITIONS.get(return_request.status, set())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                entity="ReturnRequest",
                from_status=return_request.status,
                to_status=new_status,
            )

        old_status = return_request.status
        return_request.status = new_status
        return_request.save(update_fields=["status", "modified"])

        ReturnRequestStatusHistory.objects.create(
            return_request=return_request,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )

    @classmethod
    def _validate_return_quantities(
        cls,
        order: Order,
        lines: list[ReturnLineInput],
    ) -> None:
        """
        Ensure no line requests more units than are eligible for return.

        Eligible = OrderItem.quantity - units already requested in return
        requests that are still open OR already COMPLETED (those units were
        actually returned/refunded and can't be returned again). Only
        REJECTED and CANCELLED requests are excluded, since those never
        actually took the units back.
        """
        for line in lines:
            oi = line.order_item
            if oi.order_id != order.pk:
                raise OrderNotEligibleForReturnError(
                    _("Order item %(sku)s does not belong to order %(num)s.")
                    % {"sku": oi.variant_sku, "num": order.number}
                )

            already_requested = (
                ReturnRequestItem.objects.filter(
                    order_item=oi,
                )
                .exclude(return_request__status__in=_NON_COUNTING_RETURN_STATUSES)
                .values_list("quantity_requested", flat=True)
            )
            total_already = sum(already_requested)
            max_returnable = oi.quantity - total_already

            if line.quantity_requested > max_returnable:
                raise ReturnQuantityExceededError(
                    sku=oi.variant_sku,
                    requested=line.quantity_requested,
                    max_returnable=max_returnable,
                )

    @classmethod
    def _validate_received_quantities(
        cls,
        items: list[ReturnRequestItem],
        received_quantities: dict[object, int],
    ) -> None:
        """
        Ensure every supplied qty_received is within [0, quantity_requested].

        The DB CheckConstraint (return_item_received_lte_requested) would
        also reject an out-of-range value, but only as a raw IntegrityError
        once ReturnRequestItem.save() runs -- validate up front instead, so
        a bad input is rejected cleanly before the RECEIVED transition and
        any restocking happen at all.
        """
        for item in items:
            qty_received = received_quantities.get(item.pk, 0)
            if not 0 <= qty_received <= item.quantity_requested:
                raise ReturnQuantityExceededError(
                    sku=item.order_item.variant_sku,
                    requested=qty_received,
                    max_returnable=item.quantity_requested,
                    message=str(
                        _(
                            "Cannot receive %(qty)s unit(s) of '%(sku)s': "
                            "only %(max)s unit(s) were requested for return."
                        )
                        % {
                            "qty": qty_received,
                            "sku": item.order_item.variant_sku,
                            "max": item.quantity_requested,
                        }
                    ),
                )

    @classmethod
    def _get_fulfilment_warehouse(cls, order_item: OrderItem) -> Warehouse | None:
        """Return the warehouse that dispatched this order item, or None."""

        fulfilment: Fulfilment | None = getattr(order_item, "fulfilment", None)
        if fulfilment is None:
            return None
        warehouse: Warehouse | None = fulfilment.warehouse
        return warehouse

    @classmethod
    def _maybe_restore_order_delivered(cls, order: Order) -> None:
        """Restore Order.status -> DELIVERED when no active return remains."""

        if order.status != OrderStatusEnum.RETURN_REQUESTED:
            return

        still_active = (
            ReturnRequest.objects.filter(
                order=order,
            )
            .exclude(status__in=ReturnRequest.TERMINAL_STATUSES)
            .exists()
        )

        if not still_active:
            with contextlib.suppress(InvalidStatusTransitionError):
                OrderService.transition(order, OrderStatusEnum.DELIVERED)

    @classmethod
    def _maybe_mark_order_returned(
        cls,
        order: Order,
        changed_by: StaffProfile | None = None,
    ) -> None:
        """Transition Order -> RETURNED when all return requests are terminal."""

        all_terminal = (
            not ReturnRequest.objects.filter(
                order=order,
            )
            .exclude(status__in=ReturnRequest.TERMINAL_STATUSES)
            .exists()
        )

        if all_terminal and order.status == OrderStatusEnum.RETURN_REQUESTED:
            with contextlib.suppress(InvalidStatusTransitionError):
                OrderService.transition(
                    order,
                    OrderStatusEnum.RETURNED,
                    changed_by=changed_by,
                )
