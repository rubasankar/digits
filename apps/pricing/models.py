from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from core.models import BaseModel


class Currency(UUIDModel, TimeStampedModel):
    # TODO: Multi-currency support - when the platform needs to support multiple
    #   active currencies with live exchange rates, introduce a CurrencyRate model:
    #     CurrencyRate(from_currency FK, to_currency FK, rate Decimal, effective_from
    #     DateTimeField) with a UniqueConstraint on (from_currency, to_currency,
    #     effective_from). The pricing service should then convert amounts using the
    #     latest active rate rather than relying on per-variant Pricing rows for every
    #     currency. is_active on Currency controls which currencies are available at
    #     checkout; is_default identifies the storefront base currency used for
    #     conversion source.

    code = models.CharField(
        _("Code"),
        max_length=3,
        unique=True,
        help_text=_("ISO 4217 three-letter currency code, e.g. USD."),
    )
    symbol = models.CharField(
        _("Symbol unicode"),
        max_length=10,
        help_text=_("Display symbol unicode used in prices, e.g. $ or £."),
    )
    name = models.CharField(
        _("Name"),
        max_length=50,
        help_text=_("Full English name, e.g. 'US Dollar'."),
    )
    is_default = models.BooleanField(
        _("Default Currency"),
        default=False,
        help_text=_(
            "The storefront's primary currency. "
            "Only one currency should be set as default."
        ),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        db_index=True,
        help_text=_(
            "Only active currencies are offered at checkout and used for pricing. "
            "Deactivate instead of deleting to preserve historical payment records."
        ),
    )

    class Meta:
        verbose_name = _("Currency")
        verbose_name_plural = _("Currencies")
        ordering = ["-is_default", "-is_active", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_currency",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.symbol})"

    def __repr__(self) -> str:
        return (
            f"<Currency code={self.code!r} "
            f"default={self.is_default} "
            f"active={self.is_active}>"
        )


class TaxClass(BaseModel):
    class Meta:
        verbose_name = _("Tax Class")
        verbose_name_plural = _("Tax Classes")
        ordering = ["name"]


class TaxRate(UUIDModel, TimeStampedModel):
    tax_class = models.ForeignKey(
        TaxClass,
        verbose_name=_("Tax Class"),
        on_delete=models.CASCADE,
        related_name="rates",
    )
    country = CountryField(
        _("Country"),
        help_text=_("ISO 3166-1 alpha-2 country code, e.g. 'GB', 'US', 'IN'."),
    )
    state = models.CharField(
        _("State / Province"),
        max_length=100,
        blank=True,
        help_text=_(
            "Optional. ISO 3166-2 subdivision or free-text state name. "
            "Leave blank for a country-wide rate."
        ),
    )
    rate_percent = models.DecimalField(
        _("Rate (%)"),
        max_digits=5,
        decimal_places=2,
        help_text=_("Tax percentage, e.g. 20.00 for 20%, 5.00 for 5%."),
    )
    effective_from = models.DateField(
        _("Effective From"),
        help_text=_(
            "Date this rate becomes applicable."
            "Set this deliberately -- not auto-filled."
        ),
    )
    effective_to = models.DateField(
        _("Effective To"),
        null=True,
        blank=True,
        help_text=_(
            "Date this rate expires. Leave blank if the rate has no planned end."
        ),
    )

    class Meta:
        verbose_name = _("Tax Rate")
        verbose_name_plural = _("Tax Rates")
        ordering = ["country", "state", "tax_class", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["tax_class", "country", "state", "effective_from"],
                name="unique_tax_rate_per_jurisdiction_date",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_percent__gte=0),
                name="tax_rate_percent_non_negative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if (
            self.effective_to
            and self.effective_from
            and self.effective_to < self.effective_from
        ):
            raise ValidationError(
                {
                    "effective_to": _(
                        "Effective To cannot be earlier than Effective From."
                    )
                }
            )

    def __str__(self) -> str:
        region = f"{self.country}/{self.state}" if self.state else self.country
        return f"{self.tax_class} -- {region} @ {self.rate_percent}%"

    def __repr__(self) -> str:
        return (
            f"<TaxRate id={self.id} class={self.tax_class} "
            f"country={self.country!r} state={self.state!r} "
            f"rate={self.rate_percent} from={self.effective_from}>"
        )


class Pricing(UUIDModel, TimeStampedModel):
    class PriceType(models.TextChoices):
        BASE = ("BASE", "Base Price")
        SALE = ("SALE", "Sale Price")

    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="prices",
        help_text=_(
            "The variant being priced. "
            "Tax class is resolved via: variant - product - tax_class."
        ),
    )
    currency = models.ForeignKey(
        Currency,
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        related_name="prices",
    )
    price_type = models.CharField(
        _("Price Type"),
        max_length=4,
        choices=PriceType.choices,
        default=PriceType.BASE,
    )
    amount = models.DecimalField(
        _("Amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Pre-tax price in the given currency."),
    )
    valid_from = models.DateTimeField(
        _("Valid From"),
        null=True,
        blank=True,
        help_text=_(
            "When this price becomes active. "
            "Null = active immediately. Used for SALE prices."
        ),
    )
    valid_to = models.DateTimeField(
        _("Valid To"),
        null=True,
        blank=True,
        help_text=_("When this price expires. Null = no expiry. Used for SALE prices."),
    )

    class Meta:
        verbose_name = _("Pricing")
        verbose_name_plural = _("Pricing")
        ordering = ["variant", "currency", "price_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "currency", "price_type"],
                name="unique_price_per_variant_currency_type_base_only",
                condition=models.Q(price_type="BASE"),
            ),
            models.UniqueConstraint(
                fields=["variant", "currency", "price_type", "valid_from"],
                name="unique_price_per_variant_currency_type_sale_with_date",
                condition=models.Q(price_type="SALE"),
            ),
            # Prices must be non-negative -- a negative list price makes no sense.
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="pricing_amount_non_negative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError({"valid_to": _("Valid To must be after Valid From.")})
        if self.amount is not None and self.amount < 0:
            raise ValidationError({"amount": _("Price amount cannot be negative.")})

    def __str__(self) -> str:
        price_type_label = self.PriceType(self.price_type).label
        return (
            f"{self.variant} -- {price_type_label} {self.currency.symbol}{self.amount}"
        )

    def __repr__(self) -> str:
        return (
            f"<Pricing id={self.id} variant={self.variant} "
            f"currency={self.currency} type={self.price_type} "
            f"amount={self.amount}>"
        )
