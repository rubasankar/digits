from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.admin import TabularInline

from .models import CustomerAddress
from .models import CustomerProfile


class CustomerAddressInline(TabularInline):  # type: ignore[misc]
    model = CustomerAddress
    extra = 0
    fields = [
        "address_type",
        "full_name",
        "contact_number",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "country",
        "pincode",
        "is_default",
    ]
    readonly_fields: list[str] = []


@admin.register(CustomerAddress)
class CustomerAddressAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "id",
        "customer",
        "full_name",
        "city",
        "state",
        "country",
        "address_type",
        "is_default",
    ]
    list_filter = ["address_type", "is_default", "country"]
    search_fields = [
        "full_name",
        "city",
        "state",
        "country",
        "pincode",
        "customer__first_name",
        "customer__last_name",
        "customer__user__email",
    ]
    readonly_fields = ["created", "modified"]


@admin.register(CustomerProfile)
class CustomerProfileAdmin(ModelAdmin):  # type: ignore[misc]
    list_display = [
        "full_name",
        "user",
        "gender",
        "accepts_marketing",
        "created",
    ]
    list_filter = ["gender", "accepts_marketing"]
    search_fields = ["first_name", "last_name", "user__email"]
    readonly_fields = ["created", "modified", "avatar_display"]
    inlines = [CustomerAddressInline]
    fieldsets = (
        (
            None,
            {"fields": ("user", "first_name", "last_name")},
        ),
        (
            _("Contact & Personal"),
            {"fields": ("date_of_birth", "gender")},
        ),
        (
            _("Avatar"),
            {"fields": ("avatar", "avatar_display"), "classes": ("collapse",)},
        ),
        (
            _("Marketing"),
            {
                "fields": ("accepts_marketing",),
                "description": _(
                    "This flag must only be True if the customer explicitly opted in."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description=_("Avatar"))
    def avatar_display(self, obj: CustomerProfile) -> str:
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 150px; border-radius: 8px;" />',
                obj.avatar.url,
            )
        return str(_("No avatar uploaded"))
