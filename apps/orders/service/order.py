from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

import structlog
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.catalogue.service.attribute import AttributeService
from apps.delivery.exceptions import WarehouseResolutionError
from apps.inventory.services import StockMovementService
from apps.orders.enums import OrderStatusEnum
from apps.orders.models import Order
from apps.orders.models import OrderItem
from apps.orders.models import OrderStatusHistory
from core.exceptions import InvalidStatusTransitionError

if TYPE_CHECKING:
    from apps.catalogue.models.product import ProductVariant
    from apps.customers.models import CustomerProfile
    from apps.inventory.models import Warehouse
    from apps.pricing.models import Currency
    from apps.staff.models import StaffProfile

logger = structlog.get_logger(__name__)

# Physical-group fulfilment type values (must match catalogue.enums.FulfilmentType).
_PHYSICAL_FULFILMENT_TYPES: frozenset[str] = frozenset(
    {"shipment", "local_delivery", "store_pickup"}
)

# Physical types that hand off to a carrier via the shipping app and therefore
# need a ShippingMethod selected. store_pickup is physical (consumes warehouse
# stock) but never touches the shipping app -- it's handled by delivery alone.
_CARRIER_FULFILMENT_TYPES: frozenset[str] = frozenset({"shipment", "local_delivery"})


# Data containers


@dataclass(slots=True, kw_only=True)
class OrderLineInput:
    """Input data for one order line (supplied by CheckoutService)."""

    variant: ProductVariant
    quantity: int
    unit_price: Decimal  # pre-tax, already resolved
    tax_rate: Decimal  # percentage, e.g. Decimal("20.00")
    warehouse: Warehouse | None  # None for non-physical fulfilment types


@dataclass(slots=True, kw_only=True)
class PlaceOrderInput:
    """All data required to place a new order (supplied by CheckoutService)."""

    customer: CustomerProfile
    currency: Currency
    shipping_address_snapshot: dict[str, Any]  # already serialised JSON dict
    billing_address_snapshot: dict[str, Any]  # already serialised JSON dict
    lines: list[OrderLineInput]
    shipping_cost: Decimal = Decimal("0.00")
    discount_amount: Decimal = Decimal("0.00")
    coupon_code: str = ""
    notes: str = ""
    shipping_method: uuid.UUID | None = field(default=None)
    # Name snapshot persisted onto Order.shipping_method for staff/warehouse
    # visibility; `shipping_method` above is only the id used for validation.
    shipping_method_name: str = ""


# Allowed transitions


_ORDER_TRANSITIONS: dict[str, set[str]] = {
    OrderStatusEnum.PENDING: {OrderStatusEnum.CONFIRMED, OrderStatusEnum.CANCELLED},
    OrderStatusEnum.CONFIRMED: {OrderStatusEnum.PROCESSING, OrderStatusEnum.CANCELLED},
    OrderStatusEnum.PROCESSING: {OrderStatusEnum.SHIPPED},
    OrderStatusEnum.SHIPPED: {OrderStatusEnum.DELIVERED},
    OrderStatusEnum.DELIVERED: {OrderStatusEnum.RETURN_REQUESTED},
    # DELIVERED is allowed here too: OrderReturnService restores the order to
    # DELIVERED when a return request is rejected or cancelled with no other
    # active return remaining (see _maybe_restore_order_delivered()).
    OrderStatusEnum.RETURN_REQUESTED: {
        OrderStatusEnum.RETURNED,
        OrderStatusEnum.DELIVERED,
    },
    OrderStatusEnum.CANCELLED: set(),
    OrderStatusEnum.RETURNED: set(),
}


# OrderService


class OrderService:
    # Order placement

    @classmethod
    @transaction.atomic
    def place_order(cls, data: PlaceOrderInput) -> Order:

        if not data.lines:
            raise ValueError(_("Cannot place an order with no lines."))

        # Validate: carrier-bound lines (shipment/local_delivery) require a
        # shipping_method. store_pickup is physical too but never touches a
        # carrier, so it's excluded here.
        has_carrier_line = any(
            line.variant.product.fulfilment_type in _CARRIER_FULFILMENT_TYPES
            for line in data.lines
        )
        if has_carrier_line and data.shipping_method is None:
            raise ValidationError(
                _("A shipping method is required for orders with shipped items.")
            )

        #  Compute financials
        sub_total = sum(line.unit_price * line.quantity for line in data.lines)
        tax_amount = sum(
            (line.unit_price * line.quantity * line.tax_rate / Decimal("100")).quantize(
                Decimal("0.01")
            )
            for line in data.lines
        )
        total_amount = (
            sub_total - data.discount_amount + data.shipping_cost + tax_amount
        )

        #  Create Order
        order = Order(
            number=cls._generate_order_number(),
            customer=data.customer,
            currency=data.currency,
            shipping_address=data.shipping_address_snapshot,
            billing_address=data.billing_address_snapshot,
            sub_total=sub_total,
            discount_amount=data.discount_amount,
            shipping_cost=data.shipping_cost,
            shipping_method=data.shipping_method_name,
            tax_amount=tax_amount,
            total_amount=total_amount,
            coupon_code=data.coupon_code,
            notes=data.notes,
            status=OrderStatusEnum.PENDING,
        )
        order.full_clean()
        order.save()

        #  Create OrderItems + reserve stock + create Fulfilment records
        for line in data.lines:
            variant = line.variant
            fulfilment_type: str = variant.product.fulfilment_type
            is_physical = fulfilment_type in _PHYSICAL_FULFILMENT_TYPES

            # Guard: physical lines must have a warehouse resolved by the caller.
            if is_physical and line.warehouse is None:
                msg = (
                    f"No warehouse resolved for physical-group line"
                    f" (variant={variant.pk}, fulfilment_type={fulfilment_type})."
                )
                raise WarehouseResolutionError(msg)

            attr_snapshot = AttributeService.build_attribute_snapshot(variant)

            order_item = OrderItem(
                order=order,
                variant=variant,
                variant_sku=variant.sku,
                variant_name=variant.product.name,
                variant_attributes=attr_snapshot,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
                quantity=line.quantity,
                line_total=(line.unit_price * line.quantity).quantize(Decimal("0.01")),
            )
            order_item.full_clean()
            order_item.save()

            # Reserve stock (physical lines only; warehouse is non-None here).
            if is_physical:
                StockMovementService.reserve_for_order(
                    variant=variant,
                    warehouse=line.warehouse,  # type: ignore[arg-type]
                    quantity=line.quantity,
                    order_item=order_item,
                )

            # Create the Fulfilment record for this line.
            from apps.delivery.services import FulfilmentService  # noqa: PLC0415

            FulfilmentService.create(
                order_item,
                warehouse=line.warehouse,
                fulfilment_type=fulfilment_type,
            )

        #  Initial status history row
        OrderStatusHistory.objects.create(
            order=order,
            old_status="",
            new_status=OrderStatusEnum.PENDING,
        )

        return order

    # Status transitions

    @classmethod
    @transaction.atomic
    def transition(
        cls,
        order: Order,
        new_status: str,
        *,
        changed_by: StaffProfile | None = None,
        note: str = "",
    ) -> Order:
        allowed = _ORDER_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(
                entity="Order",
                from_status=order.status,
                to_status=new_status,
            )

        old_status = order.status
        order.status = new_status
        order.save(update_fields=["status", "modified"])

        OrderStatusHistory.objects.create(
            order=order,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            note=note,
        )

        # Cancellation: cancel each cancellable fulfilment via FulfilmentService.
        if new_status == OrderStatusEnum.CANCELLED:
            cls._cancel_fulfilments(order, changed_by=changed_by)

        return order

    @classmethod
    @transaction.atomic
    def update_payment_status(
        cls,
        order: Order,
        new_payment_status: str,
    ) -> Order:
        """Sync the denormalised payment_status field on the Order."""
        order.payment_status = new_payment_status
        order.save(update_fields=["payment_status", "modified"])
        return order

    # Internal helpers

    @classmethod
    def _generate_order_number(cls) -> str:
        """Generate a unique, human-readable order number.

        Format: ORD-{8 uppercase hex chars} - e.g. ORD-3F7A1BC2.
        """
        return f"ORD-{uuid.uuid4().hex[:8].upper()}"

    @classmethod
    def _cancel_fulfilments(
        cls,
        order: Order,
        changed_by: StaffProfile | None = None,
    ) -> None:
        """Cancel each cancellable Fulfilment on the order via FulfilmentService."""

        _cancellable = {"PENDING", "ALLOCATED", "PICKED", "PACKED"}
        _skip = {"SHIPPED", "DELIVERED"}
        from apps.delivery.services import FulfilmentService  # noqa: PLC0415

        for item in order.items.select_related("fulfilment").all():
            fulfilment = getattr(item, "fulfilment", None)
            if fulfilment is None:
                continue

            if fulfilment.status in _skip:
                continue
            if fulfilment.status not in _cancellable:
                continue

            try:
                # This runs inside transition()'s outer @transaction.atomic
                # block. Wrap each cancellation in its own savepoint so a
                # DB-level failure here (e.g. IntegrityError) only rolls back
                # this fulfilment, instead of aborting the connection and
                # poisoning the outer transaction (the order's own status
                # change and history row) for every later statement.
                with transaction.atomic():
                    FulfilmentService.cancel(fulfilment, changed_by=changed_by)
            except Exception:
                logger.exception(
                    "orders.cancel_fulfilments.failed",
                    order_id=str(order.pk),
                    fulfilment_id=str(fulfilment.pk),
                )
