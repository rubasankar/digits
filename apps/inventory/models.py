from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel
from phonenumber_field.modelfields import PhoneNumberField

from apps.inventory.enums import MovementTypeEnum
from core.models import AddressBaseModel
from core.models import BaseModel


class Warehouse(BaseModel, AddressBaseModel):
    code = models.CharField(
        _("Warehouse Code"),
        max_length=20,
        unique=True,
        help_text=_("Short unique identifier used in references, e.g. 'LON-01'."),
    )
    priority = models.PositiveSmallIntegerField(
        _("Priority"),
        default=0,
        help_text=_(
            "Priority for stock allocation across multiple warehouses. "
            "Higher numbers are preferred. Default 0."
        ),
    )
    contact_person = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Contact Person"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_warehouses",
        help_text=_("Staff member responsible for this warehouse."),
    )
    contact_number = PhoneNumberField(
        _("Contact Number"),
        blank=True,
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Warehouse")
        verbose_name_plural = _("Warehouses")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def __repr__(self) -> str:
        return f"<Warehouse id={self.id} code={self.code!r}>"


class Stock(UUIDModel, TimeStampedModel):
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="stock",
    )
    warehouse = models.ForeignKey(
        Warehouse,
        verbose_name=_("Warehouse"),
        on_delete=models.CASCADE,
        related_name="stock",
    )
    quantity = models.IntegerField(
        _("Quantity on Hand"),
        default=0,
        help_text=_(
            "Total physical units at this warehouse. "
            "Updated automatically by StockMovementService -- do not edit directly."
        ),
    )
    reserved_quantity = models.PositiveIntegerField(
        _("Reserved Quantity"),
        default=0,
        help_text=_(
            "Units committed to placed but unfulfilled orders. "
            "Updated automatically by StockMovementService -- do not edit directly."
        ),
    )
    reorder_point = models.PositiveIntegerField(
        _("Reorder Point"),
        null=True,
        blank=True,
        help_text=_(
            "Low-stock alert threshold. When available quantity falls below this, "
            "alert staff to reorder. Null = no threshold."
        ),
    )
    minimum_order_qty = models.PositiveSmallIntegerField(
        _("Minimum Order Quantity"),
        default=1,
        help_text=_("Minimum units a customer must purchase per order."),
    )
    maximum_order_qty = models.PositiveSmallIntegerField(
        _("Maximum Order Quantity"),
        default=0,
        help_text=_("Maximum units per order. 0 = no limit."),
    )

    class Meta:
        verbose_name = _("Stock")
        verbose_name_plural = _("Stock")
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "warehouse"],
                name="unique_stock_per_variant_warehouse",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_quantity__lte=models.F("quantity")),
                name="stock_reserved_lte_quantity",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.variant} @ {self.warehouse.code} "
            f"-- on-hand: {self.quantity}, available: {self.available_quantity}"
        )

    def __repr__(self) -> str:
        return (
            f"<Stock id={self.id} variant={self.variant} "
            f"warehouse={self.warehouse} qty={self.quantity} "
            f"reserved={self.reserved_quantity}>"
        )

    @property
    def available_quantity(self) -> int:
        """Units available to sell = on-hand - reserved."""
        return max(0, self.quantity - self.reserved_quantity)

    @property
    def is_in_stock(self) -> bool:
        """True when at least one unit is available."""
        return self.available_quantity > 0


class StockMovement(UUIDModel, TimeStampedModel):
    MovementType = MovementTypeEnum

    # Movements that affect quantity (on-hand)
    QUANTITY_MOVEMENTS = {
        MovementType.RECEIPT,
        MovementType.SALE,
        MovementType.RETURN,
        MovementType.ADJUSTMENT_IN,
        MovementType.ADJUSTMENT_OUT,
        MovementType.TRANSFER_IN,
        MovementType.TRANSFER_OUT,
    }
    # Movements that affect reserved_quantity
    RESERVATION_MOVEMENTS = {
        MovementType.RESERVE,
        MovementType.RELEASE,
    }

    stock = models.ForeignKey(
        Stock,
        verbose_name=_("Stock"),
        on_delete=models.CASCADE,
        related_name="movements",
        help_text=_("The Stock row this movement affects."),
    )
    movement_type = models.CharField(
        _("Movement Type"),
        max_length=10,
        choices=MovementType.choices,
        db_index=True,
    )
    delta = models.PositiveIntegerField(
        _("Units"),
        help_text=_(
            "Number of units involved. Always positive -- "
            "movement_type determines whether stock increases or decreases."
        ),
    )

    # Snapshot of stock levels AFTER this movement was applied.
    # Stored so you can audit / reconstruct without replaying the ledger.
    quantity_after = models.IntegerField(_("Quantity After"), default=0)
    reserved_after = models.IntegerField(_("Reserved After"), default=0)

    # Optional references to the cause of this movement.
    order_item = models.ForeignKey(
        "orders.OrderItem",
        verbose_name=_("Order Item"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text=_("Set for SALE, RESERVE, and RELEASE movements."),
    )
    performed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Performed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text=_("Staff user who triggered this movement. Null = automated/system."),
    )
    reference = models.CharField(
        _("Reference"),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_(
            "External reference for this movement. "
            "e.g. PO number for receipts, transfer ID for transfers, "
            "RMA number for returns."
        ),
    )
    note = models.TextField(
        _("Note"),
        blank=True,
        help_text=_(
            "Reason for this movement. "
            "Required for ADJUSTMENT_IN and ADJUSTMENT_OUT movements."
        ),
    )

    class Meta:
        verbose_name = _("Stock Movement")
        verbose_name_plural = _("Stock Movements")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["stock", "-created"]),
            models.Index(fields=["movement_type", "-created"]),
            models.Index(fields=["reference"]),
        ]
        constraints = [
            # delta must be positive -- the movement type encodes direction.
            models.CheckConstraint(
                condition=models.Q(delta__gt=0),
                name="stock_movement_delta_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.delta == 0:
            raise ValidationError({"delta": _("Delta must be greater than zero.")})
        adjustment_types = {
            self.MovementType.ADJUSTMENT_IN,
            self.MovementType.ADJUSTMENT_OUT,
        }
        if self.movement_type in adjustment_types and not self.note:
            raise ValidationError(
                {"note": _("A note is required for adjustment movements.")}
            )

    def save(self, *args: object, **kwargs: object) -> None:
        """Prevent editing an existing movement -- they are immutable."""
        if self.pk:
            raise ValidationError(
                _("StockMovement records are immutable. Create a new movement instead.")
            )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"{self.get_movement_type_display()} | "
            f"{self.stock.variant} @ {self.stock.warehouse.code} | "
            f"D{self.delta} | after: {self.quantity_after}"
        )

    def __repr__(self) -> str:
        return (
            f"<StockMovement id={self.id} stock={self.stock} "
            f"type={self.movement_type} delta={self.delta}>"
        )
