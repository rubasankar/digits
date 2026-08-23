from typing import Any

from django import forms

from apps.catalogue.enums import UnitDimension
from apps.catalogue.models.attribute import AttributeDefinition

from .models.product import Product
from .models.product import ProductVariant
from .widgets import KeyValueField
from .widgets import ShippingAttributesField
from .widgets import UnitSymbolWidget


class AttributeDefinitionAdminForm(forms.ModelForm["AttributeDefinition"]):
    class Meta:
        model = AttributeDefinition
        fields = [
            "name",
            "label",
            "value_type",
            "unit_dimension",
            "unit_symbol",
        ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Determine the currently-active dimension so UnitSymbolWidget can
        # pre-populate the correct option list on first render.
        current_dim: str = UnitDimension.NONE
        if self.instance and self.instance.pk:
            current_dim = self.instance.unit_dimension or UnitDimension.NONE
        elif self.data.get("unit_dimension"):
            current_dim = self.data["unit_dimension"]

        self.fields["unit_symbol"].widget = UnitSymbolWidget(
            dimension_field_id="id_unit_dimension"
        )
        # Merge data-current-dimension into the widget's existing attrs dict
        # so it reaches render() when Django calls BoundField.as_widget().
        self.fields["unit_symbol"].widget.attrs["data-current-dimension"] = current_dim

        # Also restrict unit_dimension to a plain Select (it already is by default)
        self.fields["unit_dimension"].widget = forms.Select(
            choices=UnitDimension.choices,
            attrs={"id": "id_unit_dimension"},
        )


class ProductAdminForm(forms.ModelForm[Product]):
    other_attributes = ShippingAttributesField()

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "description",
            "category",
            "brand",
            "product_type",
            "fulfilment_type",
            "tax_class",
            "other_attributes",
            "is_active",
        ]

    def clean_other_attributes(self) -> dict[str, Any]:
        return self.cleaned_data.get("other_attributes") or {}


class ProductVariantAdminForm(forms.ModelForm[ProductVariant]):
    other_attributes = KeyValueField()

    class Meta:
        model = ProductVariant
        fields = [
            "product",
            "sku",
            "other_attributes",
            "is_active",
        ]

    def clean_other_attributes(self) -> dict[str, str]:
        return self.cleaned_data.get("other_attributes") or {}
