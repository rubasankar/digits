from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from core.exceptions import InsufficientStockError

from .enums import MovementTypeEnum
from .models import Stock
from .models import StockMovement
from .models import Warehouse

if TYPE_CHECKING:
    from apps.catalogue.models.product import ProductVariant
    from apps.orders.models import OrderItem
    from apps.staff.models import StaffProfile


@dataclass(frozen=True, slots=True)
class MovementMeta:
    """Optional metadata recorded on a stock ledger entry."""

    reference: str = ""
    note: str = ""
    order_item: OrderItem | None = None
    performed_by: StaffProfile | None = None


class StockMovementService:
    MovementType = MovementTypeEnum

    # Movements that ADD to quantity (on-hand)
    _QUANTITY_INCREASE = {
        MovementType.RECEIPT,
        MovementType.RETURN,
        MovementType.ADJUSTMENT_IN,
        MovementType.TRANSFER_IN,
    }
    # Movements that SUBTRACT from quantity (on-hand)
    _QUANTITY_DECREASE = {
        MovementType.SALE,
        MovementType.ADJUSTMENT_OUT,
        MovementType.TRANSFER_OUT,
    }
    # Movements that ADD to reserved_quantity
    _RESERVATION_INCREASE = {MovementType.RESERVE}
    # Movements that SUBTRACT from reserved_quantity
    _RESERVATION_DECREASE = {MovementType.RELEASE}

    # Stock row helpers

    @classmethod
    def get_or_create_stock(
        cls,
        variant: ProductVariant,
        warehouse: Warehouse,
    ) -> Stock:
        stock, _ = Stock.objects.get_or_create(
            variant=variant,
            warehouse=warehouse,
            defaults={"quantity": 0, "reserved_quantity": 0},
        )
        return stock

    @classmethod
    def get_available_quantity(
        cls,
        variant: ProductVariant,
        warehouse: Warehouse | None = None,
    ) -> int:
        qs = Stock.objects.filter(variant=variant)
        if warehouse is not None:
            qs = qs.filter(warehouse=warehouse)

        total = 0
        for stock in qs:
            total += stock.available_quantity
        return total

    # Core write

    @classmethod
    @transaction.atomic
    def apply(
        cls,
        *,
        stock: Stock,
        movement_type: str,
        delta: int,
        meta: MovementMeta | None = None,
    ) -> StockMovement:
        meta = meta or MovementMeta()

        if delta <= 0:
            raise ValidationError({"delta": _("Delta must be a positive integer.")})

        adjustment_types = {
            cls.MovementType.ADJUSTMENT_IN,
            cls.MovementType.ADJUSTMENT_OUT,
        }
        if movement_type in adjustment_types and not meta.note:
            raise ValidationError(
                {"note": _("A note is required for adjustment movements.")}
            )

        # Lock the row to serialise concurrent writes.
        locked_stock = Stock.objects.select_for_update().get(pk=stock.pk)

        new_quantity = locked_stock.quantity
        new_reserved = locked_stock.reserved_quantity

        if movement_type in cls._QUANTITY_INCREASE:
            new_quantity += delta

        elif movement_type in cls._QUANTITY_DECREASE:
            new_quantity -= delta
            # Quantity can go negative for manual adjustments (staff decides),
            # but SALE should never go below zero.
            if movement_type == cls.MovementType.SALE and new_quantity < 0:
                raise InsufficientStockError(
                    sku=locked_stock.variant.sku,
                    requested=delta,
                    available=locked_stock.available_quantity,
                )

        elif movement_type in cls._RESERVATION_INCREASE:
            # Cannot reserve more than what is available.
            if delta > locked_stock.available_quantity:
                raise InsufficientStockError(
                    sku=locked_stock.variant.sku,
                    requested=delta,
                    available=locked_stock.available_quantity,
                )
            new_reserved += delta

        elif movement_type in cls._RESERVATION_DECREASE:
            new_reserved = max(0, new_reserved - delta)

        else:
            raise ValidationError(
                {
                    "movement_type": _("Unknown movement type: %(t)s.")
                    % {"t": movement_type}
                }
            )

        # After computing, reserved must not exceed quantity.
        if new_reserved > new_quantity:
            raise ValidationError(
                _(
                    "Movement would result in reserved_quantity (%(r)s) "
                    "exceeding quantity (%(q)s)."
                )
                % {"r": new_reserved, "q": new_quantity}
            )

        # Write the immutable ledger entry first.
        movement = StockMovement(
            stock=locked_stock,
            movement_type=movement_type,
            delta=delta,
            quantity_after=new_quantity,
            reserved_after=new_reserved,
            reference=meta.reference,
            note=meta.note,
            order_item=meta.order_item,
            performed_by=meta.performed_by,
        )
        movement.save()  # StockMovement.save() raises if pk is set (immutability guard)

        # Update the Stock counters in the same transaction.
        Stock.objects.filter(pk=locked_stock.pk).update(
            quantity=new_quantity,
            reserved_quantity=new_reserved,
        )

        return movement

    # Convenience wrappers

    @classmethod
    @transaction.atomic
    def receive_stock(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        quantity: int,
        meta: MovementMeta | None = None,
    ) -> StockMovement:
        """Record a stock receipt (goods arrive from supplier)."""
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=cls.MovementType.RECEIPT,
            delta=quantity,
            meta=meta,
        )

    @classmethod
    @transaction.atomic
    def reserve_for_order(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        quantity: int,
        order_item: OrderItem,
    ) -> StockMovement:
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=cls.MovementType.RESERVE,
            delta=quantity,
            meta=MovementMeta(
                order_item=order_item,
                note=f"Reserved for order {order_item.order_id}",
            ),
        )

    @classmethod
    @transaction.atomic
    def release_reservation(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        quantity: int,
        order_item: OrderItem,
    ) -> StockMovement:
        """Release a reservation (order cancelled or item removed from order)."""
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=cls.MovementType.RELEASE,
            delta=quantity,
            meta=MovementMeta(
                order_item=order_item,
                note=f"Released reservation for order {order_item.order_id}",
            ),
        )

    @classmethod
    @transaction.atomic
    def record_sale(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        quantity: int,
        order_item: OrderItem,
    ) -> StockMovement:
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=cls.MovementType.SALE,
            delta=quantity,
            meta=MovementMeta(
                order_item=order_item,
                note=f"Sale dispatched for order {order_item.order_id}",
            ),
        )

    @classmethod
    @transaction.atomic
    def restock_return(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        quantity: int,
        meta: MovementMeta | None = None,
    ) -> StockMovement:
        """Restock units received back from a customer return."""
        meta = meta or MovementMeta(note="Customer return restock")
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=cls.MovementType.RETURN,
            delta=quantity,
            meta=meta,
        )

    @classmethod
    @transaction.atomic
    def adjust(
        cls,
        *,
        variant: ProductVariant,
        warehouse: Warehouse,
        delta: int,
        meta: MovementMeta,
    ) -> StockMovement:
        if delta == 0:
            raise ValidationError({"delta": _("Adjustment delta cannot be zero.")})

        movement_type = (
            cls.MovementType.ADJUSTMENT_IN
            if delta > 0
            else cls.MovementType.ADJUSTMENT_OUT
        )
        stock = cls.get_or_create_stock(variant, warehouse)
        return cls.apply(
            stock=stock,
            movement_type=movement_type,
            delta=abs(delta),
            meta=meta,
        )

    @classmethod
    @transaction.atomic
    def transfer(
        cls,
        *,
        variant: ProductVariant,
        from_warehouse: Warehouse,
        to_warehouse: Warehouse,
        quantity: int,
        meta: MovementMeta | None = None,
    ) -> tuple[StockMovement, StockMovement]:
        if from_warehouse.pk == to_warehouse.pk:
            raise ValidationError(_("Source and destination warehouse must differ."))

        meta = meta or MovementMeta()
        note = (
            f"Transfer {meta.reference}"
            if meta.reference
            else "Inter-warehouse transfer"
        )
        meta = MovementMeta(
            reference=meta.reference,
            note=note,
            performed_by=meta.performed_by,
        )

        source = cls.get_or_create_stock(variant, from_warehouse)
        dest = cls.get_or_create_stock(variant, to_warehouse)

        out = cls.apply(
            stock=source,
            movement_type=cls.MovementType.TRANSFER_OUT,
            delta=quantity,
            meta=meta,
        )
        in_ = cls.apply(
            stock=dest,
            movement_type=cls.MovementType.TRANSFER_IN,
            delta=quantity,
            meta=meta,
        )
        return out, in_

    # Preferred warehouse selection

    @classmethod
    def select_warehouse(
        cls,
        variant: ProductVariant,
        required_quantity: int,
    ) -> Warehouse | None:
        candidates = (
            Stock.objects.filter(
                variant=variant,
                warehouse__is_active=True,
            )
            .select_related("warehouse")
            .order_by("-warehouse__priority", "warehouse__name")
        )

        for stock in candidates:
            if stock.available_quantity >= required_quantity:
                return stock.warehouse

        return None
