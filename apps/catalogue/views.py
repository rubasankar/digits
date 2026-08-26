from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.catalogue.enums import AttributeValueType
from apps.catalogue.models.attribute import AttributeDefinition
from apps.catalogue.models.attribute import AttributeOption
from apps.catalogue.models.category import ProductCategory
from apps.catalogue.service.storefront import CatalogueStorefrontService
from apps.inventory.models import Stock
from apps.pricing.models import Currency
from apps.pricing.models import Pricing
from apps.reviews.models import ProductReview

if TYPE_CHECKING:
    from decimal import Decimal

    from apps.catalogue.models.product import Product
    from apps.catalogue.models.product import ProductVariant

_PRODUCTS_PER_PAGE = 24
_MAX_REVIEWS = 5

logger = logging.getLogger(__name__)


def catalogue_index(request: HttpRequest) -> HttpResponse:
    """List all active top-level categories with direct-product counts."""
    categories = (
        ProductCategory.objects.active()
        .roots()
        .annotate(
            product_count=Count(
                "products",
                filter=Q(products__is_active=True),
            )
        )
        .order_by("name")
    )
    return render(request, "catalogue/index.html", {"categories": categories})


def category_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Show products in a category, with optional search and pagination."""
    service = CatalogueStorefrontService()
    category = service.get_category_by_slug(slug)
    if category is None:
        raise Http404

    page_number = int(request.GET.get("page", 1))
    search_term = request.GET.get("q", "")

    products_qs = service.get_products_for_category(
        category,
        page=page_number,
        search=search_term,
    )

    paginator = Paginator(products_qs, _PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(page_number)

    breadcrumb_items = [
        {"label": crumb.name, "url": f"/catalogue/{crumb.slug}/"}
        for crumb in category.get_breadcrumb()
    ]

    context = {
        "category": category,
        "page_obj": page_obj,
        "search_term": search_term,
        "breadcrumb_items": breadcrumb_items,
    }
    return render(request, "catalogue/category.html", context)


def _get_available_stock(variant: ProductVariant) -> int:
    """Return available stock for a variant across all active warehouses."""
    result = Stock.objects.filter(
        variant=variant,
        warehouse__is_active=True,
    ).aggregate(total=Sum("quantity") - Sum("reserved_quantity"))
    raw = result.get("total")
    return max(0, int(raw)) if raw is not None else 0


def _get_base_price(variant: ProductVariant) -> Decimal | None:
    """Return the BASE price for a variant in the default currency."""
    pricing = Pricing.objects.filter(
        variant=variant,
        price_type=Pricing.PriceType.BASE,
        currency__is_default=True,
    ).first()
    return pricing.amount if pricing else None


def _get_variant_image_urls(variant: ProductVariant) -> list[str]:
    """Return this variant's image URLs, primary image first."""
    images = list(variant.images.all())
    urls: list[str] = []
    for img in sorted(images, key=lambda i: (not i.is_primary, i.display_order)):
        try:
            urls.append(str(img.image.url))
        except ValueError:
            continue
    return urls


def _variant_label(
    variant: ProductVariant,
    options_by_key: dict[tuple[str, str], AttributeOption],
) -> str:
    """Human label for a variant option card,
    e.g. 'Red, Large', falling back to its SKU."""
    parts = [
        options_by_key[(av.definition_id, av.value)].label
        if (av.definition_id, av.value) in options_by_key
        else av.value
        for av in variant.attribute_values.all()
        if av.definition.value_type == AttributeValueType.SINGLE_SELECT
    ]
    return ", ".join(parts) if parts else variant.sku


def _build_variant_options(
    product_variants: list[ProductVariant],
    selected_variant: ProductVariant | None,
) -> list[dict[str, object]]:
    """Build one small option-card entry per active variant, each linking to
    its own `?variant=` URL rather than swapping content client-side."""
    definition_ids = [
        av.definition_id
        for variant in product_variants
        for av in variant.attribute_values.all()
        if av.definition.value_type == AttributeValueType.SINGLE_SELECT
    ]
    options_by_key = {
        (opt.definition_id, opt.value): opt
        for opt in AttributeOption.objects.filter(definition_id__in=definition_ids)
    }

    options: list[dict[str, object]] = []
    for variant in product_variants:
        images = _get_variant_image_urls(variant)
        options.append(
            {
                "sku": variant.sku,
                "label": _variant_label(variant, options_by_key),
                "price": _get_base_price(variant),
                "image": images[0] if images else "",
                "is_selected": selected_variant is not None
                and variant.id == selected_variant.id,
            }
        )
    return options


def _get_primary_image_url(product_variants: list[ProductVariant]) -> str:
    """Find the URL of the primary image across all variants."""
    for variant in product_variants:
        for img in variant.images.all():
            if img.is_primary:
                try:
                    return str(img.image.url)
                except ValueError:
                    pass
    return ""


def _get_lowest_price(
    product_variants: list[ProductVariant],
) -> Decimal | None:
    """Return the lowest BASE price across all active variants."""
    lowest: Decimal | None = None
    for variant in product_variants:
        p = _get_base_price(variant)
        if p is not None and (lowest is None or p < lowest):
            lowest = p
    return lowest


def _get_currency_code() -> str:
    """Return the ISO code of the default currency."""
    default_currency = Currency.objects.filter(is_default=True).first()
    return default_currency.code if default_currency else ""


def _build_breadcrumbs(product: Product) -> list[dict[str, str]]:
    """Build the breadcrumb trail for a product detail page."""
    items: list[dict[str, str]] = [{"label": "Home", "url": "/"}]
    if product.category:
        items.extend(
            {"label": crumb.name, "url": f"/catalogue/{crumb.slug}/"}
            for crumb in product.category.get_breadcrumb()
        )
    items.append({"label": product.name, "url": ""})
    return items


def _select_variant(
    active_variants: list[ProductVariant], requested_sku: str
) -> ProductVariant | None:
    """Pick the variant to display: the requested SKU if valid, else the first."""
    if requested_sku:
        for variant in active_variants:
            if variant.sku == requested_sku:
                return variant
    return active_variants[0] if active_variants else None


def product_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """Show product detail for one variant at a time.

    Each variant is its own navigable state via ``?variant=<sku>`` -- picking a
    different variant is a normal link/page load, not a client-side swap.
    """
    service = CatalogueStorefrontService()
    product = service.get_product_by_slug(slug)
    if product is None:
        raise Http404

    active_variants = list(product.variants.filter(is_active=True).order_by("sku"))
    all_variants = list(product.variants.all())

    selected_variant = _select_variant(active_variants, request.GET.get("variant", ""))
    variant_options = (
        _build_variant_options(active_variants, selected_variant)
        if len(active_variants) > 1
        else []
    )

    selected_price = _get_base_price(selected_variant) if selected_variant else None
    selected_stock = (
        _get_available_stock(selected_variant)
        if selected_variant and product.is_shippable
        else None
    )
    selected_images = (
        _get_variant_image_urls(selected_variant) if selected_variant else []
    )

    primary_image_url = _get_primary_image_url(all_variants)
    lowest_price = _get_lowest_price(active_variants)
    currency_code = _get_currency_code()
    breadcrumb_items = _build_breadcrumbs(product)

    reviews = (
        ProductReview.objects.filter(product=product, is_published=True)
        .order_by("-created")
        .select_related("customer")[:_MAX_REVIEWS]
    )

    context = {
        "product": product,
        "selected_variant": selected_variant,
        "selected_price": selected_price,
        "selected_stock": selected_stock,
        "selected_images": selected_images,
        "variant_options": variant_options,
        "primary_image_url": primary_image_url,
        "lowest_price": lowest_price,
        "currency_code": currency_code,
        "breadcrumb_items": breadcrumb_items,
        "reviews": reviews,
    }
    return render(request, "catalogue/product_detail.html", context)


@require_GET
def attribute_definition_detail(request: HttpRequest, pk: str) -> HttpResponse:
    """Return attribute definition details as JSON for dynamic widget switching."""
    try:
        defn = AttributeDefinition.objects.get(pk=pk)
    except AttributeDefinition.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    options = list(
        defn.options.filter(is_active=True)
        .order_by("display_order")
        .values_list("value", flat=True)
    )
    option_labels = {
        opt.value: opt.label
        for opt in defn.options.filter(is_active=True).order_by("display_order")
    }

    return JsonResponse(
        {
            "value_type": defn.value_type,
            "options": [
                {"value": v, "label": option_labels.get(v, v)} for v in options
            ],
        }
    )
