from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Stock
from .models import StockMovement
from .models import Warehouse

if TYPE_CHECKING:
    from django.http import HttpRequest


class StockMovementInline(admin.TabularInline[StockMovement, Stock]):
    model = StockMovement
    extra = 0
    readonly_fields = (
        "movement_type",
        "delta",
        "quantity_after",
        "reserved_after",
        "order_item",
        "performed_by",
        "reference",
        "note",
        "created",
    )
    fields = readonly_fields
    ordering = ["-created"]
    can_delete = False
    max_num = 0  # No adding via inline -- use service or StockMovementAdmin.

    def has_add_permission(
        self, request: HttpRequest, obj: Stock | None = None
    ) -> bool:
        return False


class StockInline(admin.TabularInline[Stock, Warehouse]):
    model = Stock
    extra = 0
    readonly_fields = ["variant", "quantity", "reserved_quantity", "available_quantity"]
    fields = [
        "variant",
        "quantity",
        "reserved_quantity",
        "available_quantity",
        "minimum_order_qty",
        "maximum_order_qty",
    ]
    show_change_link = True

    @admin.display(description=_("Available"))
    def available_quantity(self, obj: Stock) -> int:
        return obj.available_quantity

    def has_add_permission(
        self, request: HttpRequest, obj: Warehouse | None = None
    ) -> bool:
        return False


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin[Warehouse]):
    list_display = ["name", "code", "city", "country", "is_active", "contact_person"]
    list_filter = ["is_active", "country"]
    search_fields = ["name", "code", "city"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created", "modified"]
    inlines = [StockInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "code", "description")}),
        (
            _("Address"),
            {
                "fields": (
                    "address_line1",
                    "address_line2",
                    "landmark",
                    "city",
                    "state",
                    "country",
                    "pincode",
                )
            },
        ),
        (_("Contact"), {"fields": ("contact_person", "contact_number")}),
        (_("Status"), {"fields": ("is_active",)}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin[Stock]):
    list_display = [
        "variant",
        "warehouse",
        "quantity",
        "reserved_quantity",
        "available_quantity_display",
        "is_in_stock_display",
    ]
    list_filter = ["warehouse", "warehouse__is_active"]
    search_fields = ["variant__sku", "variant__product__name", "warehouse__code"]
    readonly_fields = [
        "variant",
        "warehouse",
        "quantity",
        "reserved_quantity",
    ]
    inlines = [StockMovementInline]
    fieldsets = (
        (
            _(" Read-only -- use Stock Movements to change quantities"),
            {
                "fields": ("variant", "warehouse", "quantity", "reserved_quantity"),
                "description": _(
                    "These fields are managed by the inventory service. "
                    "To change stock, add a Stock Movement below."
                ),
            },
        ),
        (
            _("Order Limits"),
            {"fields": ("minimum_order_qty", "maximum_order_qty")},
        ),
    )

    @admin.display(description=_("Available"))
    def available_quantity_display(self, obj: Stock) -> int:
        return obj.available_quantity

    @admin.display(
        description=_("In Stock"),
        boolean=True,
    )
    def is_in_stock_display(self, obj: Stock) -> bool:
        return obj.is_in_stock

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # Stock rows are created by the service, not manually.


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin[StockMovement]):
    list_display = [
        "created",
        "movement_type",
        "stock",
        "delta",
        "quantity_after",
        "reserved_after",
        "performed_by",
        "reference",
    ]
    list_filter = ["movement_type", "stock__warehouse"]
    search_fields = [
        "stock__variant__sku",
        "stock__variant__product__name",
        "stock__warehouse__code",
        "reference",
        "note",
    ]
    readonly_fields = [
        "stock",
        "movement_type",
        "delta",
        "quantity_after",
        "reserved_after",
        "order_item",
        "performed_by",
        "reference",
        "note",
        "created",
    ]
    ordering = ["-created"]
    date_hierarchy = "created"

    fieldsets = (
        (
            _("Movement"),
            {"fields": ("stock", "movement_type", "delta")},
        ),
        (
            _("Stock Levels After"),
            {"fields": ("quantity_after", "reserved_after")},
        ),
        (
            _("Source"),
            {"fields": ("order_item", "performed_by", "reference", "note")},
        ),
        (
            _("Timestamp"),
            {"fields": ("created",)},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # Movements must be created via StockMovementService.

    def has_change_permission(
        self, request: HttpRequest, obj: StockMovement | None = None
    ) -> bool:
        return False  # Movements are immutable.

    def has_delete_permission(
        self, request: HttpRequest, obj: StockMovement | None = None
    ) -> bool:
        return False  # Movements are immutable.
