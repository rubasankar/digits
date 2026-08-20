from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from django.apps import apps as django_apps
from django.db import models
from django.db.models import Count

from .enums import ProductType

if TYPE_CHECKING:
    from .models.attribute import AttributeAssignment
    from .models.attribute import VariantAttributeValue
    from .models.category import ProductCategory
    from .models.product import Product
    from .models.product import ProductBrand
    from .models.product import ProductVariant  # noqa: F401


class ProductCategoryQuerySet(models.QuerySet["ProductCategory"]):
    def active(self) -> ProductCategoryQuerySet:
        return self.filter(is_active=True)

    def inactive(self) -> ProductCategoryQuerySet:
        return self.filter(is_active=False)

    def roots(self) -> ProductCategoryQuerySet:
        return self.filter(depth=1)

    def at_depth(self, depth: int) -> ProductCategoryQuerySet:
        return self.filter(depth=depth)

    def with_assignments(self) -> ProductCategoryQuerySet:
        # Use django_apps to avoid circular imports; AttributeAssignment imports
        # ProductCategory which in turn would import this module.
        assignment_model: type[AttributeAssignment] = django_apps.get_model(
            "catalogue", "AttributeAssignment"
        )
        return self.prefetch_related(
            models.Prefetch(
                "attribute_assignments",
                queryset=assignment_model.objects.select_related("definition"),
            )
        )

    def with_product_count(self) -> ProductCategoryQuerySet:
        return cast(
            "ProductCategoryQuerySet",
            self.annotate(product_count=Count("products")),
        )


class ProductQuerySet(models.QuerySet["Product"]):
    def active(self) -> ProductQuerySet:
        return self.filter(is_active=True)

    def inactive(self) -> ProductQuerySet:
        return self.filter(is_active=False)

    def physical(self) -> ProductQuerySet:
        return self.filter(product_type=ProductType.PHYSICAL)

    def digital(self) -> ProductQuerySet:
        return self.filter(product_type=ProductType.DIGITAL)

    def by_type(self, product_type: str) -> ProductQuerySet:
        return self.filter(product_type=product_type)

    def by_fulfilment(self, fulfilment_type: str) -> ProductQuerySet:
        return self.filter(fulfilment_type=fulfilment_type)

    def in_category(self, category: ProductCategory) -> ProductQuerySet:
        return self.filter(category=category)

    def in_category_tree(self, category: ProductCategory) -> ProductQuerySet:
        descendant_ids = list(category.get_descendants().values_list("pk", flat=True))
        category_ids = [category.pk, *descendant_ids]
        return self.filter(category_id__in=category_ids)

    def by_brand(self, brand: ProductBrand) -> ProductQuerySet:
        return self.filter(brand=brand)

    def with_category(self) -> ProductQuerySet:
        return self.select_related("category")

    def with_brand(self) -> ProductQuerySet:
        return self.select_related("brand")

    def with_relations(self) -> ProductQuerySet:
        return self.select_related("category", "brand")


class ProductVariantQuerySet(models.QuerySet["ProductVariant"]):
    def active(self) -> ProductVariantQuerySet:
        return self.filter(is_active=True)

    def inactive(self) -> ProductVariantQuerySet:
        return self.filter(is_active=False)

    def for_product(self, product: Product) -> ProductVariantQuerySet:
        return self.filter(product=product)

    def for_category(
        self,
        category: ProductCategory,
    ) -> ProductVariantQuerySet:
        return self.filter(product__category=category)

    def by_sku(self, sku: str) -> ProductVariantQuerySet:
        return self.filter(sku__iexact=sku)

    # select_related / prefetch_related presets
    def with_product(self) -> ProductVariantQuerySet:
        return self.select_related("product")

    def with_product_category(self) -> ProductVariantQuerySet:
        return self.select_related("product", "product__category")

    def with_attribute_values(self) -> ProductVariantQuerySet:
        # Use django_apps to avoid circular imports at module level.
        variant_value_model: type[VariantAttributeValue] = django_apps.get_model(
            "catalogue", "VariantAttributeValue"
        )
        return self.prefetch_related(
            models.Prefetch(
                "attribute_values",
                queryset=variant_value_model.objects.select_related("definition"),
            )
        )

    def with_primary_image(self) -> ProductVariantQuerySet:
        product_image_model = django_apps.get_model("catalogue", "ProductImage")
        return self.prefetch_related(
            models.Prefetch(
                "images",
                queryset=product_image_model.objects.filter(is_primary=True),
                to_attr="primary_images",
            )
        )

    def with_images(self) -> ProductVariantQuerySet:
        product_image_model = django_apps.get_model("catalogue", "ProductImage")
        return self.prefetch_related(
            models.Prefetch(
                "images",
                queryset=product_image_model.objects.order_by("display_order"),
            )
        )

    def with_relations(self) -> ProductVariantQuerySet:
        variant_value_model: type[VariantAttributeValue] = django_apps.get_model(
            "catalogue", "VariantAttributeValue"
        )
        product_image_model = django_apps.get_model("catalogue", "ProductImage")
        return self.select_related(
            "product", "product__category", "product__brand"
        ).prefetch_related(
            models.Prefetch(
                "attribute_values",
                queryset=variant_value_model.objects.select_related("definition"),
            ),
            models.Prefetch(
                "images",
                queryset=product_image_model.objects.order_by("display_order"),
            ),
        )
