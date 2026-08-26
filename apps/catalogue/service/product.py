from __future__ import annotations

import itertools
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.catalogue.enums import AttributeScope
from apps.catalogue.enums import FulfilmentType
from apps.catalogue.enums import ProductType
from apps.catalogue.models.attribute import AttributeAssignment
from apps.catalogue.models.attribute import AttributeOption
from apps.catalogue.models.attribute import VariantAttributeValue
from apps.catalogue.models.product import Product
from apps.catalogue.models.product import ProductImage
from apps.catalogue.models.product import ProductVariant
from apps.catalogue.service.attribute import AttributeProvision
from apps.catalogue.validators import validate_sku
from apps.catalogue.validators import validate_type_fulfilment_combination

if TYPE_CHECKING:
    from apps.catalogue.models.category import ProductCategory
    from apps.catalogue.models.product import ProductBrand
    from apps.catalogue.querysets import ProductQuerySet
    from apps.catalogue.querysets import ProductVariantQuerySet


@dataclass(slots=True, kw_only=True)
class ProductCreateData:
    name: str
    category: ProductCategory
    product_type: str = ProductType.PHYSICAL
    fulfilment_type: str = FulfilmentType.SHIPMENT
    brand: ProductBrand | None = None
    description: str = ""
    slug: str | None = None
    is_active: bool = True
    provision_attributes: bool = True
    # Arbitrary extra attributes not covered by the structured assignment system.
    other_attributes: dict[str, Any] = field(default_factory=dict)
    # SKU for the default variant that's auto-created alongside the product.
    # Defaults to the product's slug (every Product must have >= 1 variant --
    # everything downstream keys off the variant, never the product directly).
    variant_sku: str | None = None


class ProductService:
    # Creation

    @classmethod
    @transaction.atomic
    def create(cls, data: ProductCreateData) -> Product:
        validate_type_fulfilment_combination(
            data.product_type,
            data.fulfilment_type,
        )

        resolved_slug = data.slug or slugify(data.name)
        if Product.objects.filter(slug=resolved_slug).exists():
            raise ValidationError(
                {
                    "slug": _("A product with slug '%(s)s' already exists.")
                    % {"s": resolved_slug}
                }
            )

        product = Product(
            name=data.name,
            slug=resolved_slug,
            category=data.category,
            product_type=data.product_type,
            fulfilment_type=data.fulfilment_type,
            brand=data.brand,
            description=data.description,
            is_active=False,  # activated below, after attributes are provisioned
            other_attributes=data.other_attributes,
        )
        product.full_clean()
        product.save()

        if data.provision_attributes:
            AttributeProvision.provision_product_attributes(product)

        variant = VariantService.create(
            VariantCreateData(
                product=product,
                sku=data.variant_sku or resolved_slug,
                is_active=False,
                provision_attributes=data.provision_attributes,
            )
        )

        if data.is_active:
            cls.set_active(product, is_active=True)
            VariantService.set_active(variant, is_active=True)

        return product

    # Activation

    @classmethod
    @transaction.atomic
    def set_active(
        cls,
        product: Product,
        *,
        is_active: bool,
        cascade_variants: bool = False,
    ) -> Product:
        if is_active:
            missing = AttributeProvision.get_missing_required_labels(
                product, AttributeScope.PRODUCT
            )
            if missing:
                raise ValidationError(
                    {
                        "is_active": _(
                            "Cannot activate: required attributes are missing "
                            "a value: %(labels)s."
                        )
                        % {"labels": ", ".join(missing)}
                    }
                )

        product.is_active = is_active
        product.save(update_fields=["is_active", "modified"])

        if cascade_variants:
            product.variants.update(is_active=is_active)

        return product

    # Clone

    @classmethod
    @transaction.atomic
    def clone(
        cls,
        product: Product,
        *,
        new_name: str,
        new_slug: str | None = None,
    ) -> Product:
        resolved_slug = new_slug or slugify(new_name)
        if Product.objects.filter(slug=resolved_slug).exists():
            raise ValidationError(
                {
                    "slug": _("A product with slug '%(s)s' already exists.")
                    % {"s": resolved_slug}
                }
            )

        cloned = Product(
            name=new_name,
            slug=resolved_slug,
            description=product.description,
            category=product.category,
            brand=product.brand,
            product_type=product.product_type,
            fulfilment_type=product.fulfilment_type,
            is_active=False,  # clones start inactive
            other_attributes=dict(product.other_attributes),  # shallow copy
        )
        cloned.full_clean()
        cloned.save()
        return cloned

    # Category change

    @classmethod
    @transaction.atomic
    def change_category(
        cls,
        product: Product,
        new_category: ProductCategory,
    ) -> Product:
        old_category = product.category

        if old_category == new_category:
            return product

        product.category = new_category
        product.full_clean()
        product.save()

        AttributeProvision.provision_on_category_change(
            product=product,
            old_category=old_category,
            new_category=new_category,
        )

        return product

    # Retrieval

    @classmethod
    def active_for_category(
        cls,
        category: ProductCategory,
        *,
        include_subtree: bool = False,
    ) -> ProductQuerySet:
        qs = Product.objects.active().with_brand()
        if include_subtree:
            return qs.in_category_tree(category)
        return qs.in_category(category)


@dataclass(slots=True, kw_only=True)
class VariantCreateData:
    product: Product
    sku: str
    is_active: bool = True
    provision_attributes: bool = True
    # Arbitrary extra attributes not covered by the structured assignment system.
    other_attributes: dict[str, Any] = field(default_factory=dict)


class VariantService:
    # Creation

    @classmethod
    @transaction.atomic
    def create(cls, data: VariantCreateData) -> ProductVariant:
        validate_sku(data.sku)

        if ProductVariant.objects.filter(sku=data.sku).exists():
            raise ValidationError(
                {
                    "sku": _("A variant with SKU '%(sku)s' already exists.")
                    % {"sku": data.sku}
                }
            )

        variant = ProductVariant(
            product=data.product,
            sku=data.sku,
            is_active=data.is_active,
            other_attributes=data.other_attributes,
        )
        variant.full_clean()
        variant.save()

        if data.provision_attributes:
            AttributeProvision.provision_variant_attributes(variant)

        return variant

    # SKU matrix generation

    @classmethod
    @transaction.atomic
    def generate_variants(
        cls,
        product: Product,
        *,
        sku_prefix: str,
    ) -> list[ProductVariant]:
        assignments = (
            AttributeAssignment.objects.filter(
                category=product.category,
                scope=AttributeScope.VARIANT,
                generates_variants=True,
            )
            .select_related("definition")
            .order_by("display_order", "definition__name")
        )

        if not assignments.exists():
            raise ValidationError(
                _(
                    "No 'generates_variants' attribute assignments found for "
                    "category '%(c)s'. Add at least one VARIANT-scoped assignment "
                    "with generates_variants=True."
                )
                % {"c": product.category}
            )

        # Build axis -> options list
        axis_options: list[tuple[AttributeAssignment, list[AttributeOption]]] = []
        for assignment in assignments:
            options = list(
                assignment.definition.options.filter(is_active=True).order_by(
                    "display_order"
                )
            )
            if not options:
                raise ValidationError(
                    _(
                        "Assignment for '%(d)s' has generates_variants=True "
                        "but no active options."
                    )
                    % {"d": assignment.definition.label}
                )
            axis_options.append((assignment, options))

        created: list[ProductVariant] = []

        for combination in itertools.product(*[opts for _a, opts in axis_options]):
            suffix = "-".join(opt.value for opt in combination)
            sku = f"{sku_prefix}-{suffix}"

            if ProductVariant.objects.filter(sku=sku).exists():
                continue

            variant = ProductVariant(product=product, sku=sku, is_active=True)
            variant.full_clean()
            variant.save()

            # Set attribute values - use full_clean() to run model validation
            for (assignment, _options), option in zip(
                axis_options,
                combination,
                strict=False,
            ):
                attr_value = VariantAttributeValue(
                    variant=variant,
                    definition=assignment.definition,
                    value=option.value,
                )
                attr_value.full_clean()
                attr_value.save()

            created.append(variant)

        return created

    # Activation

    @classmethod
    @transaction.atomic
    def set_active(
        cls,
        variant: ProductVariant,
        *,
        is_active: bool,
    ) -> ProductVariant:
        if is_active:
            missing = AttributeProvision.get_missing_required_labels(
                variant, AttributeScope.VARIANT
            )
            if missing:
                raise ValidationError(
                    {
                        "is_active": _(
                            "Cannot activate: required attributes are missing "
                            "a value: %(labels)s."
                        )
                        % {"labels": ", ".join(missing)}
                    }
                )

        variant.is_active = is_active
        variant.save(update_fields=["is_active", "modified"])
        return variant

    # Images

    @classmethod
    @transaction.atomic
    def set_primary_image(
        cls,
        variant: ProductVariant,
        image: ProductImage,
    ) -> ProductImage:
        if image.product_variant_id != variant.pk:
            raise ValidationError(_("Image does not belong to the specified variant."))

        # Clear existing primary flag efficiently without loading each object
        ProductImage.objects.filter(product_variant=variant, is_primary=True).exclude(
            pk=image.pk
        ).update(is_primary=False)

        image.is_primary = True
        image.save(update_fields=["is_primary", "modified"])
        return image

    # Retrieval

    @classmethod
    def active_for_product(cls, product: Product) -> ProductVariantQuerySet:
        return (
            ProductVariant.objects.active()
            .for_product(product)
            .with_attribute_values()
            .with_primary_image()
        )
