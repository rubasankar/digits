from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Order
from .models import OrderItem
from .models import OrderStatusHistory

if TYPE_CHECKING:
    from django.http import HttpRequest


class OrderStatusHistoryInline(admin.TabularInline[OrderStatusHistory, Order]):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "note", "changed_at")
    fields = readonly_fields
    ordering = ["changed_at"]
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False


class OrderItemInline(admin.TabularInline[OrderItem, Order]):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "variant",
        "variant_sku",
        "variant_name",
        "variant_attributes",
        "unit_price",
        "tax_rate",
        "quantity",
        "line_total",
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True

    def has_add_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin[Order]):
    list_display = [
        "number",
        "customer",
        "status",
        "payment_status",
        "total_amount",
        "currency",
        "created",
    ]
    list_filter = ["status", "payment_status", "currency"]
    search_fields = ["number", "customer__user__email", "customer__first_name"]
    readonly_fields = [
        "number",
        "customer",
        "status",
        "payment_status",
        "shipping_address",
        "billing_address",
        "currency",
        "sub_total",
        "discount_amount",
        "shipping_cost",
        "tax_amount",
        "total_amount",
        "coupon_code",
        "notes",
        "created",
        "modified",
    ]
    ordering = ["-created"]
    date_hierarchy = "created"
    inlines = [OrderItemInline, OrderStatusHistoryInline]

    fieldsets = (
        (None, {"fields": ("number", "customer", "status", "payment_status")}),
        (_("Addresses"), {"fields": ("shipping_address", "billing_address")}),
        (
            _("Financials"),
            {
                "fields": (
                    "currency",
                    "sub_total",
                    "discount_amount",
                    "shipping_cost",
                    "tax_amount",
                    "total_amount",
                    "coupon_code",
                )
            },
        ),
        (_("Notes"), {"fields": ("notes",)}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
