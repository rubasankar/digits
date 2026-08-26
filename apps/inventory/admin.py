from typing import TYPE_CHECKING
from typing import Any

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern
from django.urls import path
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from .forms import ReceiveStockForm
from .models import Stock
from .models import StockMovement
from .models import Warehouse
from .services import MovementMeta
from .services import StockMovementService

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse
    from django.urls import URLPattern


class StockMovementInline(TabularInline):  # type: ignore[misc]
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


class StockInline(TabularInline):  # type: ignore[misc]
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
class WarehouseAdmin(ModelAdmin):  # type: ignore[misc]
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
class StockAdmin(ModelAdmin):  # type: ignore[misc]
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
        # Rows still aren't hand-editable (see readonly_fields above); "Add"
        # instead opens the Receive Stock form, which posts through
        # StockMovementService so the movement ledger stays accurate.
        return bool(super().has_add_permission(request))

    def get_urls(self) -> list[URLPattern]:
        urls: list[URLPattern] = super().get_urls()
        custom = [
            path(
                "receive/",
                self.admin_site.admin_view(self.receive_stock_view),
                name="inventory_stock_receive",
            ),
        ]
        return custom + urls

    def add_view(
        self,
        request: HttpRequest,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        return redirect(reverse("admin:inventory_stock_receive"))

    def receive_stock_view(self, request: HttpRequest) -> HttpResponse:
        if not self.has_add_permission(request):
            raise PermissionDenied

        if request.method == "POST":
            form = ReceiveStockForm(request.POST)
            if form.is_valid():
                try:
                    StockMovementService.receive_stock(
                        variant=form.cleaned_data["variant"],
                        warehouse=form.cleaned_data["warehouse"],
                        quantity=form.cleaned_data["quantity"],
                        meta=MovementMeta(
                            reference=form.cleaned_data["reference"],
                            note=form.cleaned_data["note"],
                            performed_by=getattr(request.user, "staff_profile", None),
                        ),
                    )
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    self.message_user(request, _("Stock received."))
                    return redirect(reverse("admin:inventory_stock_changelist"))
        else:
            form = ReceiveStockForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,  # noqa: SLF001
            "title": _("Receive Stock"),
            "form": form,
            "cancel_url": reverse("admin:inventory_stock_changelist"),
        }
        return TemplateResponse(
            request, "admin/inventory/stock/receive_form.html", context
        )


@admin.register(StockMovement)
class StockMovementAdmin(ModelAdmin):  # type: ignore[misc]
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
