from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import CheckoutSession


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin[CheckoutSession]):
    list_display = [
        "id",
        "cart",
        "customer",
        "status",
        "step",
        "order",
        "created",
    ]
    list_filter = ["status", "step"]
    search_fields = ["cart__id", "customer__user__email", "customer__first_name"]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["cart", "customer", "shipping_address", "billing_address"]
    ordering = ["-created"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "cart",
                    "order",
                    "customer",
                    "status",
                    "step",
                )
            },
        ),
        (
            _("Addresses"),
            {
                "fields": (
                    "shipping_address",
                    "billing_address",
                ),
            },
        ),
        (
            _("Shipping"),
            {
                "fields": (
                    "shipping_method",
                    "shipping_cost",
                ),
            },
        ),
        (
            _("Currency & Coupon"),
            {
                "fields": (
                    "currency",
                    "coupon_code",
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )
