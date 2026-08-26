from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import F
from django.db.models import Q
from django.utils import timezone

from core.exceptions import NoPriceFoundError

from .models import Currency
from .models import Pricing
from .models import TaxRate

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

    from apps.catalogue.models.product import ProductVariant


# PricingService


@dataclass(frozen=True)
class ResolvedPrice:
    """The active price for a variant in a specific currency."""

    variant_id: object
    currency_code: str
    currency_symbol: str
    amount: Decimal
    price_type: str  # "BASE" or "SALE"


class PricingService:
    @classmethod
    def get_current_price(
        cls,
        variant: ProductVariant,
        currency: Currency,
    ) -> ResolvedPrice:
        now = timezone.now()

        # 1. Active SALE price
        sale = (
            Pricing.objects.filter(
                variant=variant,
                currency=currency,
                price_type=Pricing.PriceType.SALE,
            )
            .filter(
                # valid_from is None OR valid_from <= now
                models_q_valid_from_ok(now),
            )
            .filter(
                # valid_to is None OR valid_to > now
                models_q_valid_to_ok(now),
            )
            # A dated sale (more specific) must outrank a perpetual one with no
            # valid_from; NULLS LAST keeps perpetual sales from sorting first.
            .order_by(F("valid_from").desc(nulls_last=True))
            .first()
        )
        if sale is not None:
            return ResolvedPrice(
                variant_id=variant.pk,
                currency_code=currency.code,
                currency_symbol=currency.symbol,
                amount=sale.amount,
                price_type=Pricing.PriceType.SALE,
            )

        # 2. BASE price
        base = Pricing.objects.filter(
            variant=variant,
            currency=currency,
            price_type=Pricing.PriceType.BASE,
        ).first()
        if base is not None:
            return ResolvedPrice(
                variant_id=variant.pk,
                currency_code=currency.code,
                currency_symbol=currency.symbol,
                amount=base.amount,
                price_type=Pricing.PriceType.BASE,
            )

        raise NoPriceFoundError(sku=variant.sku, currency_code=currency.code)

    @classmethod
    def get_default_currency(cls) -> Currency:
        """Return the platform's default (primary) currency."""
        try:
            return Currency.objects.get(is_default=True, is_active=True)
        except Currency.DoesNotExist as err:
            # Fall back to any active currency when default is not set.
            currency = Currency.objects.filter(is_active=True).order_by("code").first()
            if currency is None:
                raise NoPriceFoundError(
                    sku="(any)",
                    currency_code="(none)",
                    message="No active currency is configured on this platform.",
                ) from err
            return currency

    @classmethod
    def bulk_get_prices(
        cls,
        variants: list[ProductVariant],
        currency: Currency,
    ) -> dict[object, ResolvedPrice]:
        """
        Resolve prices for multiple variants in one database pass.

        Returns a dict keyed by variant pk.  Variants without any price are
        omitted from the result - callers should handle missing keys.
        """
        now = timezone.now()
        variant_ids = [v.pk for v in variants]

        # Fetch all relevant pricing rows in two queries.
        sale_rows = list(
            Pricing.objects.filter(
                variant_id__in=variant_ids,
                currency=currency,
                price_type=Pricing.PriceType.SALE,
            )
            .filter(models_q_valid_from_ok(now))
            .filter(models_q_valid_to_ok(now))
            .order_by("variant_id", F("valid_from").desc(nulls_last=True))
            .select_related("currency")
        )
        base_rows = {
            p.variant_id: p
            for p in Pricing.objects.filter(
                variant_id__in=variant_ids,
                currency=currency,
                price_type=Pricing.PriceType.BASE,
            ).select_related("currency")
        }

        # Build a sale-wins dict: first sale per variant
        # (already ordered by -valid_from).
        sale_map: dict[object, Pricing] = {}
        for row in sale_rows:
            if row.variant_id not in sale_map:
                sale_map[row.variant_id] = row

        result: dict[object, ResolvedPrice] = {}
        for vid in variant_ids:
            price_row = sale_map.get(vid)
            if price_row is None:
                price_row = base_rows.get(vid)
            if price_row is not None:
                result[vid] = ResolvedPrice(
                    variant_id=vid,
                    currency_code=currency.code,
                    currency_symbol=currency.symbol,
                    amount=price_row.amount,
                    price_type=price_row.price_type,
                )
        return result


# TaxService


@dataclass(frozen=True)
class ResolvedTaxRate:
    """The effective tax rate for a product in a jurisdiction."""

    tax_class_id: object
    country: str
    state: str
    rate_percent: Decimal


class TaxService:
    @classmethod
    def resolve_rate(
        cls,
        *,
        tax_class_id: UUID,
        country: str,
        state: str = "",
        target_date: date | None = None,
    ) -> ResolvedTaxRate | None:
        check_date = target_date or timezone.now().date()

        base_qs = TaxRate.objects.filter(
            tax_class_id=tax_class_id,
            effective_from__lte=check_date,
        ).filter(
            # effective_to is null OR effective_to >= check_date
            models_q_tax_effective_to(check_date)
        )

        # 1. Country + state
        if state:
            row = (
                base_qs.filter(country=country, state=state)
                .order_by("-effective_from")
                .first()
            )
            if row is not None:
                return ResolvedTaxRate(
                    tax_class_id=tax_class_id,
                    country=str(row.country),
                    state=row.state,
                    rate_percent=row.rate_percent,
                )

        # 2. Country only
        row = (
            base_qs.filter(country=country, state="")
            .order_by("-effective_from")
            .first()
        )
        if row is not None:
            return ResolvedTaxRate(
                tax_class_id=tax_class_id,
                country=str(row.country),
                state="",
                rate_percent=row.rate_percent,
            )

        return None

    @classmethod
    def calculate_tax_amount(
        cls,
        *,
        pre_tax_amount: Decimal,
        tax_class_id: UUID,
        country: str,
        state: str = "",
        target_date: date | None = None,
    ) -> tuple[Decimal, Decimal]:
        """
        Returns ``(tax_amount, rate_percent)`` for the given pre-tax amount.

        ``tax_amount`` is rounded to 2 decimal places.
        ``rate_percent`` is 0 when no rate is found.
        """
        resolved = cls.resolve_rate(
            tax_class_id=tax_class_id,
            country=country,
            state=state,
            target_date=target_date,
        )
        if resolved is None:
            return Decimal("0.00"), Decimal("0.00")

        rate = resolved.rate_percent
        tax_amount = (pre_tax_amount * rate / Decimal("100")).quantize(Decimal("0.01"))
        return tax_amount, rate


# CurrencyService


class CurrencyService:
    @classmethod
    @transaction.atomic
    def set_default(cls, currency: Currency) -> Currency:
        # Lock existing default to prevent concurrent race.
        existing_defaults = Currency.objects.select_for_update().filter(is_default=True)
        if currency.pk:
            existing_defaults = existing_defaults.exclude(pk=currency.pk)
        existing_default = existing_defaults.first()
        if existing_default is not None:
            existing_default.is_default = False
            existing_default.save(update_fields=["is_default"])

        if not currency.is_default:
            currency.is_default = True
            if currency.pk:
                currency.save(update_fields=["is_default"])
            else:
                currency.save()

        return currency

    @classmethod
    def get_active_currencies(cls) -> list[Currency]:
        """Return all active currencies ordered default-first, then by code."""
        return list(
            Currency.objects.filter(is_active=True).order_by("-is_default", "code")
        )


def models_q_valid_from_ok(now: object) -> Q:
    """Price is valid now: valid_from is NULL or valid_from <= now."""
    return Q(valid_from__isnull=True) | Q(valid_from__lte=now)


def models_q_valid_to_ok(now: object) -> Q:
    """Price has not expired: valid_to is NULL or valid_to > now."""
    return Q(valid_to__isnull=True) | Q(valid_to__gt=now)


def models_q_tax_effective_to(check_date: date) -> Q:
    """Tax rate has not expired: effective_to is NULL or effective_to >= date."""
    return Q(effective_to__isnull=True) | Q(effective_to__gte=check_date)
