from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Fulfilment
from .models import FulfilmentStatusHistory

if TYPE_CHECKING:
    from django.http import HttpRequest


class FulfilmentStatusHistoryInline(
    admin.TabularInline[FulfilmentStatusHistory, Fulfilment]
):
    model = FulfilmentStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "note", "changed_at")
    fields = readonly_fields
    ordering = ["changed_at"]
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Fulfilment | None = None
    ) -> bool:
        return False


@admin.register(Fulfilment)
class FulfilmentAdmin(admin.ModelAdmin[Fulfilment]):
    list_display = [
        "id",
        "order_item",
        "fulfilment_type",
        "status",
        "warehouse",
        "tracking_number",
        "shipped_at",
    ]
    list_filter = ["status", "fulfilment_type", "warehouse"]
    search_fields = [
        "id",
        "order_item__variant_sku",
        "order_item__order__number",
        "tracking_number",
        "carrier",
    ]
    readonly_fields = [
        "id",
        "order_item",
        "warehouse",
        "fulfilment_type",
        "tracking_number",
        "carrier",
        "dispatch_error",
        "allocated_at",
        "picked_at",
        "packed_at",
        "shipped_at",
        "delivered_at",
        "created",
        "modified",
    ]
    ordering = ["-created"]
    inlines = [FulfilmentStatusHistoryInline]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "order_item",
                    "fulfilment_type",
                    "status",
                    "warehouse",
                )
            },
        ),
        (_("Shipping"), {"fields": ("tracking_number", "carrier")}),
        (_("Dispatch Error"), {"fields": ("dispatch_error",)}),
        (
            _("Timestamps"),
            {
                "fields": (
                    "allocated_at",
                    "picked_at",
                    "packed_at",
                    "shipped_at",
                    "delivered_at",
                    "created",
                    "modified",
                )
            },
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
