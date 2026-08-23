from typing import TYPE_CHECKING
from typing import Any
from typing import cast
from typing import override

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Campaign
from .models import Coupon
from .models import Discount

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


class DiscountInline(admin.TabularInline[Discount, Campaign]):
    model = Discount
    extra = 0
    fields = [
        "discount_type",
        "applies_to",
        "value",
        "target_product",
        "target_category",
        "target_variant",
        "minimum_cart_value",
        "max_discount_amount",
    ]
    show_change_link = True


class CouponInline(admin.TabularInline[Coupon, Discount]):
    model = Coupon
    extra = 0
    fields = [
        "code",
        "usage_limit_total",
        "usage_limit_per_user",
        "valid_from",
        "valid_to",
        "is_active",
    ]
    show_change_link = True


# CouponRedemptionInline is omitted because CouponRedemption references orders.Order
# which may not be fully loaded at import time. Coupon redemptions should be
# viewed through the admin's list view instead.


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin[Campaign]):
    list_display = ["name", "start_date", "end_date", "is_active", "discount_count"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["created", "modified"]
    ordering = ["-start_date"]
    inlines = [DiscountInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        (_("Schedule"), {"fields": ("start_date", "end_date", "is_active")}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=_("Discounts"))
    def discount_count(self, obj: Campaign) -> int:
        return int(cast("Any", obj).discounts.count())

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: Campaign,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin[Discount]):
    list_display = [
        "campaign",
        "discount_type",
        "applies_to",
        "value",
        "minimum_cart_value",
        "coupon_count",
    ]
    list_filter = ["discount_type", "applies_to", "campaign"]
    search_fields = ["campaign__name"]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = [
        "campaign",
        "target_product",
        "target_category",
        "target_variant",
    ]
    ordering = ["-created"]
    inlines = [CouponInline]
    fieldsets = (
        (None, {"fields": ("campaign", "discount_type", "value")}),
        (
            _("Target"),
            {
                "fields": (
                    "applies_to",
                    "target_product",
                    "target_category",
                    "target_variant",
                ),
                "description": _(
                    "Set EXACTLY ONE target field matching the applies_to selection. "
                    "Leave all blank for CART discounts."
                ),
            },
        ),
        (
            _("Guards"),
            {"fields": ("minimum_cart_value", "max_discount_amount")},
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=_("Coupons"))
    def coupon_count(self, obj: Discount) -> int:
        return int(cast("Any", obj).coupons.count())

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: Discount,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin[Coupon]):
    list_display = [
        "code",
        "discount",
        "usage_limit_total",
        "usage_limit_per_user",
        "valid_from",
        "valid_to",
        "is_active",
        "redemption_count",
    ]
    list_filter = ["is_active", "discount__campaign"]
    search_fields = ["code", "discount__campaign__name"]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["discount"]
    ordering = ["-valid_from"]
    fieldsets = (
        (None, {"fields": ("discount", "code", "is_active")}),
        (
            _("Usage Limits"),
            {"fields": ("usage_limit_total", "usage_limit_per_user")},
        ),
        (_("Validity"), {"fields": ("valid_from", "valid_to")}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=_("Redeemed"))
    def redemption_count(self, obj: Coupon) -> int:
        return int(cast("Any", obj).redemptions.count())

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: Coupon,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)
