from __future__ import annotations

from typing import TYPE_CHECKING

from django import template

from apps.inventory.services import StockMovementService
from apps.pricing.models import Pricing

if TYPE_CHECKING:
    from decimal import Decimal

    from apps.catalogue.models.product import Product
    from apps.catalogue.models.product import ProductVariant

register = template.Library()


@register.simple_tag
def variant_base_price(variant: ProductVariant) -> Decimal | None:
    """Return the BASE price for a variant in the default currency, or None."""
    pricing = (
        Pricing.objects.filter(
            variant=variant,
            price_type=Pricing.PriceType.BASE,
            currency__is_default=True,
        )
        .select_related("currency")
        .first()
    )
    return pricing.amount if pricing else None


@register.simple_tag
def default_variant(product: Product) -> ProductVariant | None:
    """Return the product's first active variant, or None."""
    return product.variants.active().order_by("sku").first()


@register.simple_tag
def variant_available_stock(variant: ProductVariant) -> int:
    """Return total available stock for a variant across active warehouses.

    Only meaningful for shippable products -- callers should check
    `product.is_shippable` first, since digital/service products carry no
    inventory at all.
    """
    return StockMovementService.get_available_quantity(variant)
