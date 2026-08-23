from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.catalogue.enums import SELECT_VALUE_TYPES
from apps.catalogue.enums import AttributeScope
from apps.catalogue.enums import AttributeValueType
from apps.catalogue.models.attribute import AttributeAssignment
from apps.catalogue.models.attribute import AttributeDefinition
from apps.catalogue.models.attribute import AttributeOption
from apps.catalogue.models.attribute import ProductAttributeValue
from apps.catalogue.models.attribute import VariantAttributeValue
from apps.catalogue.validators import validate_attribute_name
from apps.catalogue.validators import validate_option_value

if TYPE_CHECKING:
    from uuid import UUID

    from apps.catalogue.models.category import ProductCategory
    from apps.catalogue.models.product import Product
    from apps.catalogue.models.product import ProductVariant


@dataclass(slots=True, kw_only=True)
class AttributeAssignmentCreateData:
    definition: AttributeDefinition
    category: ProductCategory
    scope: str = AttributeScope.VARIANT
    is_required: bool = False
    is_filterable: bool = False
    is_searchable: bool = False
    generates_variants: bool = False
    visible_on_listing: bool = False
    visible_on_detail: bool = True
    display_order: int = 0
    default_value: str = ""


class AttributeResolution:
    @staticmethod
    def get_category_assignments(
        category: ProductCategory,
        scope: str | None = None,
    ) -> Any:

        qs = AttributeAssignment.objects.filter(category=category)

        if scope:
            qs = qs.filter(scope=scope)

        return qs.select_related("definition").order_by(
            "display_order", "definition__name"
        )

    @staticmethod
    def get_product_assignments(
        product: Product,
        scope: str | None = None,
    ) -> Any:
        qs = AttributeAssignment.objects.filter(category=product.category)

        if scope:
            qs = qs.filter(scope=scope)

        return qs.select_related("definition").order_by(
            "display_order", "definition__name"
        )

    @staticmethod
    def get_variant_assignments(
        variant: ProductVariant,
        scope: str | None = None,
    ) -> Any:
        qs = AttributeAssignment.objects.filter(category=variant.product.category)

        if scope:
            qs = qs.filter(scope=scope)

        return qs.select_related("definition").order_by(
            "display_order", "definition__name"
        )

    @classmethod
    def resolve_product_attributes(
        cls,
        product: Product,
    ) -> dict[int, dict[str, Any]]:
        category_assignments = cls.get_category_assignments(
            product.category,
            scope=AttributeScope.PRODUCT,
        )

        result: dict[int, dict[str, Any]] = {}
        for assignment in category_assignments:
            defn = assignment.definition
            result[defn.id] = {
                "definition": defn,
                "assignment": assignment,
                "value": None,
            }

        # Populate stored values
        for data in result.values():
            data["value"] = AttributeValueService.get_product_value(
                product=product,
                definition=data["definition"],
            )

        return result

    @classmethod
    def resolve_variant_attributes(
        cls,
        variant: ProductVariant,
    ) -> dict[int, dict[str, Any]]:
        category_assignments = cls.get_category_assignments(
            variant.product.category,
            scope=AttributeScope.VARIANT,
        )

        result: dict[int, dict[str, Any]] = {}
        for assignment in category_assignments:
            defn = assignment.definition
            result[defn.id] = {
                "definition": defn,
                "assignment": assignment,
                "value": None,
            }

        # Populate stored values
        for data in result.values():
            data["value"] = AttributeValueService.get_variant_value(
                variant=variant,
                definition=data["definition"],
            )

        return result

    @classmethod
    def get_applicable_definitions(
        cls,
        product: Product,
        scope: str | None = None,
    ) -> list[AttributeDefinition]:
        resolved = cls.resolve_product_attributes(product)

        if scope:
            return [
                data["definition"]
                for data in resolved.values()
                if data["assignment"].scope == scope
            ]

        return [data["definition"] for data in resolved.values()]


class AttributeValueService:
    @classmethod
    def get_product_value(
        cls,
        product: Product,
        definition: AttributeDefinition,
    ) -> str | None:
        try:
            return ProductAttributeValue.objects.get(
                product=product,
                definition=definition,
            ).value
        except ProductAttributeValue.DoesNotExist:
            return None

    @classmethod
    def get_variant_value(
        cls,
        variant: ProductVariant,
        definition: AttributeDefinition,
    ) -> str | None:
        try:
            return VariantAttributeValue.objects.get(
                variant=variant,
                definition=definition,
            ).value
        except VariantAttributeValue.DoesNotExist:
            return None

    @classmethod
    @transaction.atomic
    def set_product_value(
        cls,
        product: Product,
        definition: AttributeDefinition,
        value: str,
    ) -> ProductAttributeValue:

        obj, _created = ProductAttributeValue.objects.update_or_create(
            product=product,
            definition=definition,
            defaults={"value": value},
        )
        return obj

    @classmethod
    @transaction.atomic
    def set_variant_value(
        cls,
        variant: ProductVariant,
        definition: AttributeDefinition,
        value: str,
    ) -> VariantAttributeValue:

        obj, _created = VariantAttributeValue.objects.update_or_create(
            variant=variant,
            definition=definition,
            defaults={"value": value},
        )
        return obj


class AttributeProvision:
    @classmethod
    @transaction.atomic
    def provision_product_attributes(
        cls,
        product: Product,
    ) -> list[ProductAttributeValue]:
        category_assignments = AttributeAssignment.objects.filter(
            category=product.category,
            scope=AttributeScope.PRODUCT,
        ).select_related("definition")

        created: list[ProductAttributeValue] = []

        for assignment in category_assignments:
            defn = assignment.definition

            if ProductAttributeValue.objects.filter(
                product=product, definition=defn
            ).exists():
                continue

            value = ProductAttributeValue(
                product=product,
                definition=defn,
                value=assignment.default_value or "",
            )
            value.full_clean()
            value.save()
            created.append(value)

        return created

    @classmethod
    @transaction.atomic
    def provision_variant_attributes(
        cls,
        variant: ProductVariant,
    ) -> list[VariantAttributeValue]:
        category_assignments = AttributeAssignment.objects.filter(
            category=variant.product.category,
            scope=AttributeScope.VARIANT,
        ).select_related("definition")

        created: list[VariantAttributeValue] = []

        for assignment in category_assignments:
            defn = assignment.definition

            if VariantAttributeValue.objects.filter(
                variant=variant, definition=defn
            ).exists():
                continue

            value = VariantAttributeValue(
                variant=variant,
                definition=defn,
                value=assignment.default_value or "",
            )
            value.full_clean()
            value.save()
            created.append(value)

        return created

    @classmethod
    def _create_value_if_missing(
        cls,
        variant: ProductVariant,
        assignment: AttributeAssignment,
        created: list[VariantAttributeValue],
    ) -> None:

        if VariantAttributeValue.objects.filter(
            variant=variant, definition=assignment.definition
        ).exists():
            return

        value = VariantAttributeValue(
            variant=variant,
            definition=assignment.definition,
            value=assignment.default_value or "",
        )
        value.full_clean()
        value.save()
        created.append(value)

    @classmethod
    @transaction.atomic
    def provision_on_category_change(
        cls,
        product: Product,
        old_category: ProductCategory | None,
        new_category: ProductCategory,
    ) -> dict[str, Any]:
        old_defn_ids: set[UUID] = set()
        if old_category:
            old_defn_ids = set(
                AttributeAssignment.objects.filter(
                    category=old_category,
                    scope=AttributeScope.PRODUCT,
                ).values_list("definition_id", flat=True)
            )

        new_assignments = AttributeAssignment.objects.filter(
            category=new_category,
            scope=AttributeScope.PRODUCT,
        ).select_related("definition")

        new_defn_ids = {a.definition_id for a in new_assignments}
        to_provision = new_defn_ids - old_defn_ids

        created: list[ProductAttributeValue] = []
        for assignment in new_assignments:
            if assignment.definition_id not in to_provision:
                continue

            if ProductAttributeValue.objects.filter(
                product=product, definition=assignment.definition
            ).exists():
                continue

            value = ProductAttributeValue(
                product=product,
                definition=assignment.definition,
                value=assignment.default_value or "",
            )
            value.full_clean()
            value.save()
            created.append(value)

        preserved_defn_ids = old_defn_ids & new_defn_ids
        preserved = list(
            ProductAttributeValue.objects.filter(
                product=product,
                definition_id__in=preserved_defn_ids,
            )
        )

        return {
            "added": created,
            "unchanged": preserved,
        }


class AttributeValidation:
    @classmethod
    def validate_assignment_scope(
        cls,
        assignment: AttributeAssignment,
    ) -> bool:
        return bool(assignment.category_id)

    @classmethod
    def validate_assignment_uniqueness(
        cls,
        definition: AttributeDefinition,
        target: ProductCategory,
    ) -> bool:
        return AttributeAssignment.objects.filter(
            definition=definition,
            category=target,
        ).exists()

    @classmethod
    def validate_required_attributes(
        cls,
        product: Product,
    ) -> dict[str, Any]:
        required_assignments = AttributeAssignment.objects.filter(
            category=product.category,
            scope=AttributeScope.PRODUCT,
            is_required=True,
        ).select_related("definition")

        missing = []
        for assignment in required_assignments:
            defn = assignment.definition
            has_value = (
                ProductAttributeValue.objects.filter(
                    product=product,
                    definition=defn,
                )
                .exclude(value="")
                .exists()
            )

            if not has_value:
                missing.append(defn.label)

        return {
            "valid": len(missing) == 0,
            "missing": missing,
        }

    @classmethod
    def validate_required_variant_attributes(
        cls,
        variant: ProductVariant,
    ) -> dict[str, Any]:
        required_assignments = AttributeAssignment.objects.filter(
            category=variant.product.category,
            scope=AttributeScope.VARIANT,
            is_required=True,
        ).select_related("definition")

        all_required = list(required_assignments)

        missing = []
        for assignment in all_required:
            defn = assignment.definition
            has_value = (
                VariantAttributeValue.objects.filter(
                    variant=variant,
                    definition=defn,
                )
                .exclude(value="")
                .exists()
            )

            if not has_value:
                missing.append(defn.label)

        return {
            "valid": len(missing) == 0,
            "missing": missing,
        }


class AttributeService:
    # AttributeDefinition

    @classmethod
    @transaction.atomic
    def create_definition(
        cls,
        *,
        name: str,
        label: str,
        value_type: str = AttributeValueType.TEXT,
        unit_symbol: str = "",
    ) -> AttributeDefinition:

        validate_attribute_name(name)

        if AttributeDefinition.objects.filter(name=name).exists():
            raise ValidationError(
                {
                    "name": _(
                        "An attribute definition with name '%(n)s' already exists."
                    )
                    % {"n": name}
                }
            )

        defn = AttributeDefinition(
            name=name,
            label=label,
            value_type=value_type,
            unit_symbol=unit_symbol,
        )
        defn.full_clean()
        defn.save()
        return defn

    @classmethod
    @transaction.atomic
    def update_definition(
        cls,
        definition: AttributeDefinition,
        *,
        label: str | None = None,
        unit_symbol: str | None = None,
    ) -> AttributeDefinition:

        if label is not None:
            definition.label = label
        if unit_symbol is not None:
            definition.unit_symbol = unit_symbol
        definition.full_clean()
        definition.save(update_fields=["label", "unit_symbol", "modified"])
        return definition

    # AttributeOption

    @classmethod
    @transaction.atomic
    def add_option(
        cls,
        definition: AttributeDefinition,
        *,
        label: str,
        value: str,
        display_order: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> AttributeOption:

        if definition.value_type not in SELECT_VALUE_TYPES:
            raise ValidationError(
                _(
                    "Options can only be added to SINGLE_SELECT or MULTI_SELECT "
                    "definitions (got '%(t)s')."
                )
                % {"t": definition.value_type}
            )

        validate_option_value(value)

        if definition.options.filter(value=value).exists():
            raise ValidationError(
                {
                    "value": _(
                        "Option value '%(v)s' already exists on this definition."
                    )
                    % {"v": value}
                }
            )

        option = AttributeOption(
            definition=definition,
            label=label,
            value=value,
            display_order=display_order,
            metadata=metadata or {},
        )
        option.full_clean()
        option.save()
        return option

    @classmethod
    @transaction.atomic
    def deactivate_option(cls, option: AttributeOption) -> AttributeOption:

        option.is_active = False
        option.save(update_fields=["is_active", "modified"])
        return option

    # AttributeAssignment  (category-scoped only)

    @classmethod
    @transaction.atomic
    def assign_to_category(
        cls,
        data: AttributeAssignmentCreateData,
    ) -> AttributeAssignment:
        assignment, _ = AttributeAssignment.objects.get_or_create(
            definition=data.definition,
            category=data.category,
            scope=data.scope,  # part of unique_together - must be a lookup key
            defaults={
                "is_required": data.is_required,
                "is_filterable": data.is_filterable,
                "is_searchable": data.is_searchable,
                "generates_variants": data.generates_variants,
                "visible_on_listing": data.visible_on_listing,
                "visible_on_detail": data.visible_on_detail,
                "display_order": data.display_order,
                "default_value": data.default_value,
            },
        )
        return assignment

    @classmethod
    def get_category_assignments(
        cls,
        category: ProductCategory,
        scope: str | None = None,
    ) -> Any:

        qs = (
            AttributeAssignment.objects.filter(category=category)
            .select_related("definition")
            .order_by("display_order", "definition__name")
        )

        if scope:
            qs = qs.filter(scope=scope)
        return qs

    # Value resolution helpers

    @classmethod
    def resolve_value(
        cls,
        definition: AttributeDefinition,
        variant: ProductVariant,
    ) -> str | None:
        # 1. Variant-level value
        try:
            return VariantAttributeValue.objects.get(
                variant=variant, definition=definition
            ).value
        except VariantAttributeValue.DoesNotExist:
            pass

        # 2. Product-level value
        try:
            return ProductAttributeValue.objects.get(
                product=variant.product, definition=definition
            ).value
        except ProductAttributeValue.DoesNotExist:
            pass

        # 3. Category assignment default
        try:
            assignment = AttributeAssignment.objects.get(
                definition=definition,
                category=variant.product.category,
            )
        except AttributeAssignment.DoesNotExist:
            return None
        else:
            return assignment.default_value or None

    @classmethod
    def build_attribute_snapshot(
        cls,
        variant: ProductVariant,
    ) -> dict[str, str]:
        product = variant.product
        assignments = (
            AttributeAssignment.objects.filter(category=product.category)
            .select_related("definition")
            .order_by("display_order")
        )

        result: dict[str, str] = {}
        for assignment in assignments:
            defn = assignment.definition
            value = cls.resolve_value(defn, variant)
            if value:
                key = (
                    f"{defn.label} ({defn.unit_display})"
                    if defn.unit_display
                    else defn.label
                )
                result[key] = value
        return result

    # Provision wrappers (backwards-compatibility shims)

    @classmethod
    @transaction.atomic
    def provision_all_product_values(
        cls,
        product: Product,
    ) -> list[ProductAttributeValue]:

        return AttributeProvision.provision_product_attributes(product)

    @classmethod
    @transaction.atomic
    def provision_all_variant_values(
        cls,
        variant: ProductVariant,
    ) -> list[VariantAttributeValue]:

        return AttributeProvision.provision_variant_attributes(variant)
