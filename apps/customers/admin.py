from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import CustomerAddress
from .models import CustomerProfile


class CustomerAddressInline(admin.TabularInline[CustomerAddress, CustomerProfile]):
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
    readonly_fields = []


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin[CustomerProfile]):
    list_display = [
        "full_name",
        "user",
        "phone_number",
        "gender",
        "accepts_marketing",
        "created",
    ]
    list_filter = ["gender", "accepts_marketing"]
    search_fields = ["first_name", "last_name", "user__email", "phone_number"]
    readonly_fields = ["created", "modified"]
    inlines = [CustomerAddressInline]
    fieldsets = (
        (
            None,
            {"fields": ("user", "first_name", "last_name")},
        ),
        (
            _("Contact & Personal"),
            {"fields": ("phone_number", "date_of_birth", "gender", "avatar")},
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
