from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from .models import CarrierAccount
from .models import Shipment
from .models import ShippingMethod
from .models import TrackingEvent

if TYPE_CHECKING:
    from django.http import HttpRequest


class TrackingEventInline(TabularInline):  # type: ignore[misc]
    model = TrackingEvent
    extra = 0
    readonly_fields = ("event_code", "event_timestamp", "description", "raw_payload")
    fields = readonly_fields
    ordering = ["event_timestamp"]
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Shipment | None = None
    ) -> bool:
        return False


@admin.register(Shipment)
class ShipmentAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "id",
        "fulfilment",
        "shipping_method",
        "tracking_number",
        "label_generated_at",
        "requested_at",
    ]
    list_filter = ["shipping_method", "label_generated_at"]
    search_fields = ["id", "tracking_number", "carrier_reference", "fulfilment__id"]
    readonly_fields = [
        "id",
        "fulfilment",
        "shipping_method",
        "tracking_number",
        "label_url",
        "label_data",
        "requested_at",
        "label_generated_at",
        "carrier_reference",
        "label_error",
        "created",
        "modified",
    ]
    ordering = ["-requested_at"]
    inlines = [TrackingEventInline]

    fieldsets = (
        (None, {"fields": ("id", "fulfilment", "shipping_method")}),
        (
            _("Label"),
            {
                "fields": (
                    "tracking_number",
                    "label_url",
                    "label_generated_at",
                    "carrier_reference",
                    "label_error",
                )
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("requested_at", "created", "modified")},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


@admin.register(ShippingMethod)
class ShippingMethodAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "name",
        "carrier",
        "is_active",
        "estimated_days_min",
        "estimated_days_max",
        "base_rate",
        "currency",
    ]
    list_filter = ["is_active", "carrier"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(CarrierAccount)
class CarrierAccountAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ["name", "carrier_code", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "carrier_code"]
    ordering = ["name"]
    readonly_fields = ["id", "created", "modified"]

    def get_exclude(
        self, request: HttpRequest, obj: CarrierAccount | None = None
    ) -> list[str]:
        return ["credentials"]
