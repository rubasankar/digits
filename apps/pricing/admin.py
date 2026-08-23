from typing import TYPE_CHECKING
from typing import Any
from typing import override

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.pricing.services import CurrencyService

from .models import Currency
from .models import Pricing
from .models import TaxClass
from .models import TaxRate

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin[Currency]):
    list_display = ["code", "name", "symbol", "is_default"]
    list_filter = ["is_default"]
    search_fields = ["code", "name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("code", "name", "symbol")}),
        (
            _("Default"),
            {
                "fields": ("is_default",),
                "description": _(
                    "Only one currency can be set as default. "
                    "This is the storefront's primary currency."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: Currency,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        """Atomically swap the default-currency flag.

        Delegates to CurrencyService so the business rule (only one default)
        is enforced consistently whether called from admin or application code.
        """

        if obj.is_default:
            CurrencyService.set_default(obj)
        else:
            super().save_model(request, obj, form, change)


@admin.register(TaxClass)
class TaxClassAdmin(admin.ModelAdmin[TaxClass]):
    list_display = ["name", "description"]
    search_fields = ["name", "slug", "description"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin[TaxRate]):
    list_display = [
        "tax_class",
        "country",
        "state",
        "rate_percent",
        "effective_from",
        "effective_to",
    ]
    list_filter = ["tax_class", "country", "state"]
    search_fields = ["country", "state", "tax_class__name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (None, {"fields": ("tax_class", "country", "state")}),
        (
            _("Rate"),
            {"fields": ("rate_percent",)},
        ),
        (
            _("Validity"),
            {
                "fields": ("effective_from", "effective_to"),
                "description": _(
                    "Set 'Effective To' to expire this rate. Leave blank for no expiry."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: TaxRate,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)


@admin.register(Pricing)
class PricingAdmin(admin.ModelAdmin[Pricing]):
    list_display = [
        "variant",
        "currency",
        "price_type",
        "amount",
        "valid_from",
        "valid_to",
    ]
    list_filter = ["price_type", "currency"]
    search_fields = ["variant__sku", "variant__product__name", "currency__code"]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["variant"]
    fieldsets = (
        (None, {"fields": ("variant", "currency", "price_type")}),
        (
            _("Amount"),
            {"fields": ("amount",)},
        ),
        (
            _("Validity"),
            {
                "fields": ("valid_from", "valid_to"),
                "description": _(
                    "Leave blank for immediate/ongoing pricing. "
                    "Used for time-based sale prices."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    @override
    def save_model(
        self,
        request: HttpRequest,
        obj: Pricing,
        form: forms.ModelForm[Any],
        change: bool,
    ) -> None:
        try:
            obj.full_clean()
        except ValidationError as exc:
            form._update_errors(exc)  # type: ignore[attr-defined]  # noqa: SLF001
            return
        super().save_model(request, obj, form, change)
