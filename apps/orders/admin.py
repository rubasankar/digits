from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from apps.orders.enums import OrderStatusEnum
from apps.orders.service.order import OrderService
from apps.orders.service.order_return import ReturnRequestService
from core.exceptions import InvalidStatusTransitionError

from .models import Order
from .models import OrderItem
from .models import OrderStatusHistory
from .models import ReturnRequest
from .models import ReturnRequestItem
from .models import ReturnRequestStatusHistory
from .models import ReturnShipment

if TYPE_CHECKING:
    from django.http import HttpRequest

    from apps.staff.models import StaffProfile


class OrderStatusHistoryInline(TabularInline):  # type: ignore[misc]
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


class OrderItemInline(TabularInline):  # type: ignore[misc]
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
class OrderAdmin(ModelAdmin):  # type: ignore[misc]
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
        "shipping_method",
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
    actions = ["mark_processing", "cancel_orders"]

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
                    "shipping_method",
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

    def has_delete_permission(
        self, request: HttpRequest, obj: Order | None = None
    ) -> bool:
        return False

    @admin.action(description=_("Mark selected orders as Processing"))
    def mark_processing(self, request: HttpRequest, queryset: Any) -> None:
        self._bulk_transition(request, queryset, OrderStatusEnum.PROCESSING)

    @admin.action(description=_("Cancel selected orders"))
    def cancel_orders(self, request: HttpRequest, queryset: Any) -> None:
        self._bulk_transition(request, queryset, OrderStatusEnum.CANCELLED)

    def _bulk_transition(
        self, request: HttpRequest, queryset: Any, new_status: str
    ) -> None:
        staff_profile = getattr(request.user, "staff_profile", None)
        succeeded = 0
        skipped = 0
        for order in queryset:
            try:
                OrderService.transition(order, new_status, changed_by=staff_profile)
            except InvalidStatusTransitionError:
                skipped += 1
            else:
                succeeded += 1
        self.message_user(
            request,
            _("%(ok)d order(s) updated, %(skip)d skipped (invalid transition).")
            % {"ok": succeeded, "skip": skipped},
        )


class ReturnRequestItemInline(TabularInline):  # type: ignore[misc]
    model = ReturnRequestItem
    extra = 0
    readonly_fields = (
        "order_item",
        "quantity_requested",
        "quantity_received",
        "condition_note",
    )
    fields = readonly_fields
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: ReturnRequest | None = None
    ) -> bool:
        return False


class ReturnShipmentInline(TabularInline):  # type: ignore[misc]
    model = ReturnShipment
    extra = 0
    readonly_fields = (
        "tracking_number",
        "carrier",
        "shipped_at",
        "expected_at",
        "received_at",
        "received_by",
        "notes",
    )
    fields = readonly_fields
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: ReturnRequest | None = None
    ) -> bool:
        return False


class ReturnRequestStatusHistoryInline(TabularInline):  # type: ignore[misc]
    model = ReturnRequestStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "note", "changed_at")
    fields = readonly_fields
    ordering = ["changed_at"]
    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: ReturnRequest | None = None
    ) -> bool:
        return False


@admin.register(ReturnRequest)
class ReturnRequestAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "id",
        "order",
        "requested_by",
        "reason",
        "status",
        "created",
    ]
    list_filter = ["status", "reason"]
    search_fields = ["order__number", "requested_by__user__email"]
    readonly_fields = [
        "order",
        "requested_by",
        "reason",
        "customer_note",
        "status",
        "reviewed_by",
        "staff_note",
        "approved_at",
        "received_at",
        "completed_at",
        "created",
        "modified",
    ]
    ordering = ["-created"]
    date_hierarchy = "created"
    inlines = [
        ReturnRequestItemInline,
        ReturnShipmentInline,
        ReturnRequestStatusHistoryInline,
    ]
    actions = [
        "approve_requests",
        "reject_requests",
        "receive_requests",
        "complete_requests",
    ]

    fieldsets = (
        (
            None,
            {"fields": ("order", "requested_by", "reason", "customer_note", "status")},
        ),
        (_("Staff Review"), {"fields": ("reviewed_by", "staff_note")}),
        (
            _("Timestamps"),
            {
                "fields": (
                    "approved_at",
                    "received_at",
                    "completed_at",
                    "created",
                    "modified",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: ReturnRequest | None = None
    ) -> bool:
        return False

    @admin.action(description=_("Approve selected return requests"))
    def approve_requests(self, request: HttpRequest, queryset: Any) -> None:
        staff_profile = cast(
            "StaffProfile", getattr(request.user, "staff_profile", None)
        )
        self._bulk_action(
            request,
            queryset,
            lambda rr: ReturnRequestService.approve(rr, reviewed_by=staff_profile),
        )

    @admin.action(description=_("Reject selected return requests"))
    def reject_requests(self, request: HttpRequest, queryset: Any) -> None:
        staff_profile = cast(
            "StaffProfile", getattr(request.user, "staff_profile", None)
        )
        self._bulk_action(
            request,
            queryset,
            lambda rr: ReturnRequestService.reject(rr, reviewed_by=staff_profile),
        )

    @admin.action(
        description=_(
            "Mark selected as received (accepts each line's full requested quantity)"
        )
    )
    def receive_requests(self, request: HttpRequest, queryset: Any) -> None:
        staff_profile = cast(
            "StaffProfile", getattr(request.user, "staff_profile", None)
        )

        def _receive(rr: ReturnRequest) -> None:
            quantities: dict[object, int] = dict(
                rr.items.values_list("pk", "quantity_requested")
            )
            ReturnRequestService.receive(
                rr,
                received_by=staff_profile,
                received_quantities=quantities,
            )

        self._bulk_action(request, queryset, _receive)

    @admin.action(description=_("Complete selected return requests"))
    def complete_requests(self, request: HttpRequest, queryset: Any) -> None:
        staff_profile = getattr(request.user, "staff_profile", None)
        self._bulk_action(
            request,
            queryset,
            lambda rr: ReturnRequestService.complete(rr, changed_by=staff_profile),
        )

    def _bulk_action(self, request: HttpRequest, queryset: Any, action: Any) -> None:
        succeeded = 0
        skipped = 0
        for return_request in queryset:
            try:
                action(return_request)
            except InvalidStatusTransitionError:
                skipped += 1
            else:
                succeeded += 1
        self.message_user(
            request,
            _("%(ok)d return request(s) updated,%(skip)d skipped (invalid transition).")
            % {"ok": succeeded, "skip": skipped},
        )
