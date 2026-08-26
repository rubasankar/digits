from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from .models import Payment
from .models import PaymentMethod
from .models import PaymentStatusHistory
from .models import Refund
from .models import RefundReason

if TYPE_CHECKING:
    from django.http import HttpRequest


class PaymentStatusHistoryInline(TabularInline):  # type: ignore[misc]
    model = PaymentStatusHistory
    extra = 0
    readonly_fields = (
        "old_status",
        "new_status",
        "changed_by",
        "gateway_event",
        "note",
        "changed_at",
    )
    fields = readonly_fields
    ordering = ["changed_at"]
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        return False


class RefundInline(TabularInline):  # type: ignore[misc]
    model = Refund
    extra = 0
    readonly_fields = (
        "transaction_id",
        "amount",
        "reason",
        "notes",
        "status",
        "refunded_by",
        "created",
    )
    fields = readonly_fields
    show_change_link = True
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        return False


@admin.register(PaymentMethod)
class PaymentMethodAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ["name", "gateway_code", "is_active", "display_order"]
    list_filter = ["is_active"]
    search_fields = ["name", "gateway_code"]
    ordering = ["display_order", "name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("name", "gateway_code", "description")}),
        (
            _("Visibility"),
            {
                "fields": ("is_active", "display_order"),
                "description": _(
                    "Inactive methods are hidden from checkout but existing "
                    "payment records keep their method."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


@admin.register(RefundReason)
class RefundReasonAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = ["name", "requires_return", "is_active", "display_order"]
    list_filter = ["is_active", "requires_return"]
    search_fields = ["name"]
    ordering = ["display_order", "name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        (
            _("Behaviour"),
            {
                "fields": ("requires_return", "is_active", "display_order"),
                "description": _(
                    "'Requires Item Return' prompts staff to confirm the "
                    "item has been received before processing the refund."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "transaction_id",
        "order",
        "gateway",
        "payment_method",
        "amount",
        "currency",
        "status",
        "initiated_at",
    ]
    list_filter = ["status", "gateway", "payment_method", "currency"]
    search_fields = ["transaction_id", "order__number", "order__customer__user__email"]
    readonly_fields = [
        "order",
        "gateway",
        "transaction_id",
        "status",
        "amount",
        "currency",
        "payment_method",
        "raw_response",
        "initiated_at",
        "completed_at",
        "created",
        "modified",
    ]
    ordering = ["-initiated_at"]
    date_hierarchy = "initiated_at"
    inlines = [PaymentStatusHistoryInline, RefundInline]
    fieldsets = (
        (None, {"fields": ("order", "gateway", "transaction_id", "status")}),
        (_("Amount"), {"fields": ("amount", "currency", "payment_method")}),
        (
            _("Timestamps"),
            {"fields": ("initiated_at", "completed_at", "created", "modified")},
        ),
        (
            _("Gateway Response"),
            {"fields": ("raw_response",), "classes": ("collapse",)},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Payment | None = None
    ) -> bool:
        return False


@admin.register(Refund)
class RefundAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "id",
        "payment",
        "amount",
        "reason",
        "status",
        "refunded_by",
        "created",
    ]
    list_filter = ["status", "reason"]
    search_fields = [
        "payment__transaction_id",
        "payment__order__number",
        "transaction_id",
    ]
    readonly_fields = [
        "payment",
        "transaction_id",
        "amount",
        "reason",
        "notes",
        "status",
        "refunded_by",
        "created",
        "modified",
    ]
    autocomplete_fields = ["reason", "refunded_by"]
    ordering = ["-created"]
    fieldsets = (
        (None, {"fields": ("payment", "transaction_id", "amount", "reason", "notes")}),
        (_("Status"), {"fields": ("status", "refunded_by")}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Refund | None = None
    ) -> bool:
        return False
