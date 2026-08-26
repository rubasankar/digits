from __future__ import annotations

from typing import cast

from django.db.models import Exists
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import QuerySet

from apps.catalogue.models.category import ProductCategory
from apps.catalogue.models.product import Product
from apps.catalogue.models.product import ProductImage
from apps.catalogue.models.product import ProductVariant


class CatalogueStorefrontService:
    """Read-only service for storefront catalogue queries."""

    MAX_LIMIT = 100
    MAX_SEARCH_LENGTH = 200

    def get_featured_categories(self, limit: int) -> QuerySet[ProductCategory]:
        """Return active featured root categories up to limit."""
        if not 1 <= limit <= self.MAX_LIMIT:
            msg = f"limit must be 1-{self.MAX_LIMIT}, got {limit}"
            raise ValueError(msg)
        return cast(
            "QuerySet[ProductCategory]",
            ProductCategory.objects.filter(
                is_active=True,
                is_featured=True,
                depth=1,
            ).select_related("default_tax_class")[:limit],
        )

    def get_featured_products(self, limit: int) -> QuerySet[Product]:
        """Return active featured products that have a primary image."""
        if not 1 <= limit <= self.MAX_LIMIT:
            msg = f"limit must be 1-{self.MAX_LIMIT}, got {limit}"
            raise ValueError(msg)
        active_variant = ProductVariant.objects.filter(
            product=OuterRef("pk"), is_active=True
        )
        primary_image = ProductImage.objects.filter(
            product_variant__product=OuterRef("pk"), is_primary=True
        )
        return (
            Product.objects.filter(
                is_active=True,
                is_featured=True,
            )
            .filter(Exists(active_variant))
            .filter(Exists(primary_image))
            .select_related("category", "brand")
            .prefetch_related("variants__prices", "variants__images")[:limit]
        )

    def get_category_by_slug(self, slug: str) -> ProductCategory | None:
        """Return an active category by slug or None."""
        try:
            return cast(
                "ProductCategory",
                ProductCategory.objects.get(slug=slug, is_active=True),
            )
        except ProductCategory.DoesNotExist:
            return None

    def get_products_for_category(
        self,
        category: ProductCategory,
        page: int,
        search: str,
    ) -> QuerySet[Product]:
        """Return active products in category tree, optionally filtered by search."""
        if page < 1:
            msg = f"page must be >= 1, got {page}"
            raise ValueError(msg)
        if len(search) > self.MAX_SEARCH_LENGTH:
            msg = f"search term must be at most {self.MAX_SEARCH_LENGTH} characters"
            raise ValueError(msg)
        descendants = category.get_descendants(include_self=True)
        active_variant = ProductVariant.objects.filter(
            product=OuterRef("pk"), is_active=True
        )
        qs = (
            Product.objects.filter(
                is_active=True,
                category__in=descendants,
            )
            .filter(Exists(active_variant))
            .select_related("category", "brand")
            .prefetch_related("variants__prices", "variants__images")
            .order_by("name")
        )
        term = search.strip()
        if term:
            qs = qs.filter(Q(name__icontains=term) | Q(description__icontains=term))
        return qs

    def get_product_by_slug(self, slug: str) -> Product | None:
        """Return an active product with prefetched variants and images, or None."""
        active_variant = ProductVariant.objects.filter(
            product=OuterRef("pk"), is_active=True
        )
        try:
            return (
                Product.objects.filter(is_active=True)
                .filter(Exists(active_variant))
                .select_related("category", "brand", "tax_class")
                .prefetch_related(
                    "variants__prices",
                    "variants__images",
                    "variants__stock",
                    "variants__attribute_values__definition",
                    "reviews",
                )
                .get(slug=slug)
            )
        except Product.DoesNotExist:
            return None
