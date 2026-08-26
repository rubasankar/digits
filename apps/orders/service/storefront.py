from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from apps.orders.models import Order
from apps.orders.models import OrderItem
from apps.orders.models import ReturnRequest
from apps.orders.service.order_return import ReturnLineInput
from apps.orders.service.order_return import ReturnRequestService

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.customers.models import CustomerProfile

_MAX_REASON_LEN = 500
_MAX_NOTE_LEN = 2000


class OrderStorefrontService:
    """Storefront-facing order queries and actions."""

    PAGE_SIZE = 20

    def get_orders_for_customer(
        self,
        customer: CustomerProfile,
        page: int,
    ) -> QuerySet[Order]:
        """Return paginated orders for a customer, newest first."""
        if page < 1:
            msg = f"page must be >= 1, got {page}"
            raise ValueError(msg)
        return (
            Order.objects.filter(customer=customer)
            .prefetch_related("items")
            .order_by("-created")
        )

    def get_order_detail(
        self,
        customer: CustomerProfile,
        number: str,
    ) -> Order | None:
        """Return a single order belonging to customer, or None."""
        try:
            return (
                Order.objects.filter(customer=customer, number=number)
                .prefetch_related(
                    "items",
                    "status_history",
                    "return_requests",
                )
                .get()
            )
        except Order.DoesNotExist:
            return None

    @transaction.atomic
    def create_return_request(
        self,
        customer: CustomerProfile,
        order: Order,
        items: list[OrderItem],
        reason: str,
        note: str,
    ) -> ReturnRequest:
        """
        Create a ReturnRequest for the customer's selected items.

        Delegates to ReturnRequestService.create(), which enforces order
        ownership/eligibility, rejects a second active return, validates
        per-line quantities, and transitions the order to RETURN_REQUESTED --
        none of which a hand-rolled .objects.create() here would get for free.
        """
        if len(reason) > _MAX_REASON_LEN:
            msg = f"reason must be at most {_MAX_REASON_LEN} characters"
            raise ValueError(msg)
        if len(note) > _MAX_NOTE_LEN:
            msg = f"note must be at most {_MAX_NOTE_LEN} characters"
            raise ValueError(msg)
        if not items:
            msg = "At least one item must be selected for return."
            raise ValueError(msg)

        lines = [
            ReturnLineInput(order_item=item, quantity_requested=item.quantity)
            for item in items
        ]
        return ReturnRequestService.create(
            order=order,
            customer=customer,
            reason=reason,
            lines=lines,
            customer_note=note,
        )
