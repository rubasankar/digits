from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.catalogue.constants import ATTRIBUTE_LABEL_MAX_LENGTH
from apps.catalogue.constants import ATTRIBUTE_NAME_MAX_LENGTH
from apps.catalogue.constants import ATTRIBUTE_SCOPE_MAX_LENGTH
from apps.catalogue.constants import ATTRIBUTE_UNIT_DIMENSION_MAX_LENGTH
from apps.catalogue.constants import ATTRIBUTE_UNIT_SYMBOL_MAX_LENGTH
from apps.catalogue.constants import ATTRIBUTE_VALUE_TYPE_MAX_LENGTH
from apps.catalogue.constants import CONSTRAINT_UNIQUE_ATTRIBUTE_OPTION_VALUE
from apps.catalogue.constants import CONSTRAINT_UNIQUE_PRODUCT_ATTRIBUTE_VALUE
from apps.catalogue.constants import CONSTRAINT_UNIQUE_VARIANT_ATTRIBUTE_VALUE
from apps.catalogue.enums import SELECT_VALUE_TYPES
from apps.catalogue.enums import UNITS_BY_DIMENSION
from apps.catalogue.enums import AttributeScope
from apps.catalogue.enums import AttributeValueType
from apps.catalogue.enums import UnitDimension
from apps.catalogue.models.mixins import AttributeAssignmentMixin
from apps.catalogue.models.mixins import AttributeValueMixin
from apps.catalogue.validators import validate_attribute_name
from apps.catalogue.validators import validate_option_value
from apps.catalogue.validators import validate_unit_symbol
from apps.catalogue.validators import validate_unit_symbol_matches_dimension


class AttributeDefinition(UUIDModel, TimeStampedModel):
    ValueType = AttributeValueType

    name = models.CharField(
        _("Attribute Name"),
        max_length=ATTRIBUTE_NAME_MAX_LENGTH,
        unique=True,
        validators=[validate_attribute_name],
        help_text=_(
            "Unique internal key. Use lowercase with underscores, "
            "e.g. 'colour', 'storage_capacity', 'material'."
        ),
    )
    label = models.CharField(
        _("Display Label"),
        max_length=ATTRIBUTE_LABEL_MAX_LENGTH,
        help_text=_(
            "Customer-facing label shown in the storefront and admin, "
            "e.g. 'Colour', 'Storage Capacity (GB)', 'Material'."
        ),
    )
    value_type = models.CharField(
        _("Value Type"),
        max_length=ATTRIBUTE_VALUE_TYPE_MAX_LENGTH,
        choices=AttributeValueType.choices,
        default=AttributeValueType.TEXT,
        help_text=_(
            "Determines the widget, validation, and coercion applied to values. "
            "SINGLE_SELECT / MULTI_SELECT require AttributeOption rows."
        ),
    )
    unit_dimension = models.CharField(
        _("Unit Dimension"),
        max_length=ATTRIBUTE_UNIT_DIMENSION_MAX_LENGTH,
        choices=UnitDimension.choices,
        default=UnitDimension.NONE,
        db_index=True,
        help_text=_(
            "Measurement category for this attribute. "
            "Selecting a dimension filters the Unit Symbol choices to "
            "only those that belong to that category. "
            "Leave as 'None / Dimensionless' for text, colour, or select attributes."
        ),
    )
    unit_symbol = models.CharField(
        _("Unit Symbol"),
        max_length=ATTRIBUTE_UNIT_SYMBOL_MAX_LENGTH,
        blank=True,
        default="",
        validators=[validate_unit_symbol],
        help_text=_(
            "Pint-recognised unit symbol displayed after numeric values, "
            "e.g. 'kilogram' -> 'kg', 'centimeter' -> 'cm'. "
            "Must belong to the selected Unit Dimension. "
            "Leave blank for attributes that have no unit."
        ),
    )

    class Meta:
        verbose_name = _("Attribute Definition")
        verbose_name_plural = _("Attribute Definitions")
        ordering = ["name"]

    # Helpers

    @property
    def unit_display(self) -> str:
        if not self.unit_symbol:
            return ""
        for sym, label in UNITS_BY_DIMENSION.get(self.unit_dimension, []):
            if sym == self.unit_symbol:
                return label
        return self.unit_symbol  # fallback to raw pint symbol

    # Validation

    def clean(self) -> None:
        super().clean()

        # If a symbol is set, it must belong to the selected dimension.
        # When dimension is NONE, only the symbols listed under NONE
        # (percent, ppm, dimensionless) are allowed - not symbols from
        # other dimension groups.
        if self.unit_symbol:
            validate_unit_symbol_matches_dimension(
                self.unit_dimension, self.unit_symbol
            )

    def __str__(self) -> str:
        unit_str = f" ({self.unit_display})" if self.unit_display else ""
        return f"{self.label}{unit_str} [{self.get_value_type_display()}]"

    def __repr__(self) -> str:
        return (
            f"<AttributeDefinition id={self.id} name={self.name!r} "
            f"type={self.value_type} dimension={self.unit_dimension}>"
        )


class AttributeOption(UUIDModel, TimeStampedModel):
    definition = models.ForeignKey(
        AttributeDefinition,
        verbose_name=_("Attribute Definition"),
        on_delete=models.CASCADE,
        related_name="options",
    )
    label = models.CharField(
        _("Label"),
        max_length=100,
        help_text=_("Customer-facing display name, e.g. 'Signal Red'."),
    )
    value = models.CharField(
        _("Value"),
        max_length=100,
        validators=[validate_option_value],
        help_text=_(
            "Machine key stored in the attribute value field, e.g. 'signal_red'. "
            "Do not change after values have been saved against this option."
        ),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Inactive options are hidden from new selections but existing "
            "attribute values that reference this option remain valid."
        ),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Lower numbers appear first in select widgets."),
    )
    metadata = models.JSONField(
        _("Metadata"),
        default=dict,
        blank=True,
        help_text=_(
            "Optional arbitrary data, e.g. {'hex': '#FF0000'} for colour swatches."
        ),
    )

    class Meta:
        verbose_name = _("Attribute Option")
        verbose_name_plural = _("Attribute Options")
        ordering = ["definition", "display_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["definition", "value"],
                name=CONSTRAINT_UNIQUE_ATTRIBUTE_OPTION_VALUE,
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.definition_id and self.definition.value_type not in SELECT_VALUE_TYPES:
            raise ValidationError(
                _(
                    "Options can only be added to SINGLE_SELECT or MULTI_SELECT "
                    "attribute definitions (got '%(t)s')."
                )
                % {"t": self.definition.value_type}
            )

    def __str__(self) -> str:
        return f"{self.definition.label}: {self.label}"

    def __repr__(self) -> str:
        return (
            f"<AttributeOption id={self.id} "
            f"definition={self.definition_id} "
            f"value={self.value!r} active={self.is_active}>"
        )


class AttributeAssignment(AttributeAssignmentMixin, UUIDModel, TimeStampedModel):
    definition = models.ForeignKey(
        AttributeDefinition,
        verbose_name=_("Attribute Definition"),
        on_delete=models.PROTECT,
        related_name="assignments",
    )
    scope = models.CharField(
        _("Scope"),
        max_length=ATTRIBUTE_SCOPE_MAX_LENGTH,
        choices=AttributeScope.choices,
        default=AttributeScope.VARIANT,
        help_text=_(
            "PRODUCT: same value for every variant. "
            "VARIANT: what makes variants different."
        ),
    )
    category = models.ForeignKey(
        "catalogue.ProductCategory",
        verbose_name=_("Category"),
        on_delete=models.CASCADE,
        related_name="attribute_assignments",
    )

    class Meta:
        verbose_name = _("Category Assignment")
        verbose_name_plural = _("Category Assignments")
        ordering = ["display_order", "definition__name"]
        unique_together = ["category", "definition", "scope"]

    def __str__(self) -> str:
        return f"{self.definition} ({self.scope}) -> {self.category}"

    def __repr__(self) -> str:
        return (
            f"<CategoryAssignment id={self.id} "
            f"definition={self.definition_id} "
            f"scope={self.scope} "
            f"category={self.category_id}>"
        )


class ProductAttributeValue(AttributeValueMixin, UUIDModel, TimeStampedModel):
    product = models.ForeignKey(
        "catalogue.Product",
        verbose_name=_("Product"),
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )
    definition = models.ForeignKey(
        "catalogue.AttributeDefinition",
        verbose_name=_("Attribute"),
        on_delete=models.CASCADE,
        related_name="product_values",
    )

    class Meta:
        verbose_name = _("Product Attribute Value")
        verbose_name_plural = _("Product Attribute Values")
        ordering = ["product", "definition__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "definition"],
                name=CONSTRAINT_UNIQUE_PRODUCT_ATTRIBUTE_VALUE,
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self._validate_value()

        if not self.definition_id or not self.product_id:
            return

        defn = self.definition
        product = self.product

        # Check if the definition is assigned at
        # PRODUCT scope to this product's category
        assigned = AttributeAssignment.objects.filter(
            definition=defn,
            scope=AttributeScope.PRODUCT,
            category=product.category,
        ).exists()

        if not assigned:
            raise ValidationError(
                _(
                    "This attribute is not assigned to this "
                    "product's category at PRODUCT scope."
                )
            )

    def __str__(self) -> str:
        unit = f"{self.definition.unit_display}" if self.definition.unit_display else ""
        return f"{self.product.name} | {self.definition.label}: {self.value}{unit}"

    def __repr__(self) -> str:
        return (
            f"<ProductAttributeValue id={self.id} "
            f"product={self.product_id} "
            f"definition={self.definition_id} "
            f"value={self.value!r}>"
        )


class VariantAttributeValue(AttributeValueMixin, UUIDModel, TimeStampedModel):
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.CASCADE,
        related_name="attribute_values",
    )
    definition = models.ForeignKey(
        "catalogue.AttributeDefinition",
        verbose_name=_("Attribute"),
        on_delete=models.CASCADE,
        related_name="variant_values",
    )

    class Meta:
        verbose_name = _("Variant Attribute Value")
        verbose_name_plural = _("Variant Attribute Values")
        ordering = ["variant", "definition__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["variant", "definition"],
                name=CONSTRAINT_UNIQUE_VARIANT_ATTRIBUTE_VALUE,
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self._validate_value()

        if not self.definition_id or not self.variant_id:
            return

        defn = self.definition
        product = self.variant.product

        # Check if the definition is assigned at
        # VARIANT scope to this variant's category
        assigned = AttributeAssignment.objects.filter(
            definition=defn,
            scope=AttributeScope.VARIANT,
            category=product.category,
        ).exists()

        if not assigned:
            raise ValidationError(
                _(
                    "This attribute is not assigned "
                    "to this variant's category at VARIANT scope."
                )
            )

    def __str__(self) -> str:
        if self.definition.unit_display:
            unit = f" {self.definition.unit_display}"
        else:
            unit = ""
        return f"{self.variant.sku} | {self.definition.label}: {self.value}{unit}"

    def __repr__(self) -> str:
        return (
            f"<VariantAttributeValue id={self.id} "
            f"variant={self.variant_id} "
            f"definition={self.definition_id} "
            f"value={self.value!r}>"
        )
