from __future__ import annotations

import contextlib
from typing import Any
from typing import cast

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from apps.catalogue.forms import ProductAdminForm
from apps.catalogue.forms import ProductVariantAdminForm

from .enums import SELECT_VALUE_TYPES
from .enums import AttributeScope
from .enums import AttributeValueType
from .forms import AttributeDefinitionAdminForm
from .models.attribute import AttributeAssignment
from .models.attribute import AttributeDefinition
from .models.attribute import AttributeOption
from .models.attribute import ProductAttributeValue
from .models.attribute import VariantAttributeValue
from .models.category import ProductCategory
from .models.product import Product
from .models.product import ProductBrand
from .models.product import ProductImage
from .models.product import ProductVariant


class AttributeOptionInline(admin.TabularInline[AttributeOption, AttributeDefinition]):
    model = AttributeOption
    extra = 1
    fields = ["label", "value", "is_active", "display_order", "metadata"]
    ordering = ["display_order", "label"]

    def get_queryset(self, request: Any) -> Any:
        return super().get_queryset(request).select_related("definition")


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin[AttributeDefinition]):
    form = AttributeDefinitionAdminForm

    list_display = [
        "name",
        "label",
        "value_type",
        "unit_dimension",
        "unit_display_col",
        "option_count",
    ]
    list_filter = ["value_type", "unit_dimension"]
    search_fields = ["name", "label"]
    ordering = ["name"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (
            None,
            {"fields": ("name", "label", "value_type")},
        ),
        (
            _("Unit"),
            {
                "fields": ("unit_dimension", "unit_symbol"),
                "description": _(
                    "1. Pick the measurement category. "
                    "2. The Unit Symbol dropdown will update to show only "
                    "units that belong to that category. "
                    "Leave both blank for text, colour, or select-type attributes."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def get_inlines(self, request: Any, obj: AttributeDefinition | None) -> list[Any]:
        if obj is not None and obj.value_type in SELECT_VALUE_TYPES:
            return [AttributeOptionInline]
        return []

    def get_queryset(self, request: Any) -> Any:
        return super().get_queryset(request).prefetch_related("options")

    @admin.display(description=_("Unit"), ordering="unit_symbol")
    def unit_display_col(self, obj: AttributeDefinition) -> str:
        return obj.unit_display or "-"

    @admin.display(description=_("Options"))
    def option_count(self, obj: AttributeDefinition) -> int:
        return len(obj.options.all())


@admin.register(AttributeAssignment)
class AttributeAssignmentAdmin(admin.ModelAdmin[AttributeAssignment]):
    list_display = [
        "definition",
        "scope",
        "target_display",
        "is_required",
        "is_filterable",
        "generates_variants",
        "display_order",
    ]
    list_filter = ["scope", "is_required", "is_filterable", "generates_variants"]
    search_fields = [
        "definition__name",
        "definition__label",
    ]
    autocomplete_fields = ["definition"]
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (
            None,
            {"fields": ("definition", "scope")},
        ),
        (
            _("Target category"),
            {"fields": ("category",)},
        ),
        (
            _("Behaviour flags"),
            {
                "fields": (
                    "is_required",
                    "is_searchable",
                    "is_filterable",
                    "is_comparable",
                    "visible_on_listing",
                    "visible_on_detail",
                    "allow_override",
                    "generates_variants",
                    "default_value",
                    "display_order",
                )
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request: Any) -> Any:
        return super().get_queryset(request).select_related("definition", "category")

    @admin.display(description=_("Target"))
    def target_display(self, obj: AttributeAssignment) -> str:
        if obj.category_id:
            return f"Category: {obj.category}"
        return "-"


@admin.register(ProductBrand)
class ProductBrandAdmin(admin.ModelAdmin[ProductBrand]):
    list_display = ["name", "website", "created"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created", "modified"]
    fieldsets = (
        (
            None,
            {"fields": ("name", "slug", "description", "website", "logo")},
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )


class AttributeAssignmentInline(
    admin.TabularInline[AttributeAssignment, ProductCategory]
):
    model = AttributeAssignment
    extra = 1
    fields = [
        "definition",
        "scope",
        "is_required",
        "is_filterable",
        "is_searchable",
        "generates_variants",
        "visible_on_listing",
        "visible_on_detail",
        "display_order",
    ]
    ordering = ["display_order", "definition__name"]
    autocomplete_fields = ["definition"]

    def get_queryset(self, request: Any) -> Any:
        return super().get_queryset(request).select_related("definition")


@admin.register(ProductCategory)
class ProductCategoryAdmin(TreeAdmin):  # type: ignore[misc]
    form = movenodeform_factory(ProductCategory)
    list_display = ["name", "slug", "depth", "is_active", "assignment_count"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    inlines = [AttributeAssignmentInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        (
            _("Position"),
            {"fields": ("treebeard_position", "treebeard_ref_node")},
        ),
        (
            _("Display"),
            {"fields": ("image", "is_active")},
        ),
    )

    def get_queryset(self, request: Any) -> Any:
        return (
            super()
            .get_queryset(request)
            .annotate(_assignment_count=Count("attribute_assignments"))
        )

    @admin.display(description=_("Attributes"), ordering="_assignment_count")
    def assignment_count(self, obj: ProductCategory) -> int:
        return int(cast("Any", obj)._assignment_count)  # noqa: SLF001


def apply_value_widget(
    fields: dict[str, forms.Field],
    defn: AttributeDefinition,
) -> None:
    vt = defn.value_type
    vtype = AttributeValueType

    if vt == vtype.BOOLEAN:
        fields["value"].widget = forms.Select(
            choices=[("true", _("Yes")), ("false", _("No"))]
        )
    elif vt in (vtype.DECIMAL, vtype.FLOAT):
        fields["value"].widget = forms.NumberInput(attrs={"step": "0.0001"})
    elif vt in (vtype.INTEGER, vtype.BIG_INTEGER):
        fields["value"].widget = forms.NumberInput(attrs={"step": "1"})
    elif vt == vtype.SINGLE_SELECT:
        choices = [("", "---------")] + [
            (opt.value, opt.label)
            for opt in defn.options.filter(is_active=True).order_by("display_order")
        ]
        fields["value"].widget = forms.Select(choices=choices)
    elif vt == vtype.MULTI_SELECT:
        choices = [
            (opt.value, opt.label)
            for opt in defn.options.filter(is_active=True).order_by("display_order")
        ]
        fields["value"].widget = forms.CheckboxSelectMultiple(choices=choices)
    elif vt == vtype.LONG_TEXT:
        fields["value"].widget = forms.Textarea(attrs={"rows": 4})
    elif vt == vtype.COLOR:
        fields["value"].widget = forms.TextInput(attrs={"type": "color"})
    # TEXT, EMAIL, URL, UUID, DATE, TIME, DATETIME, JSON: default TextInput.


def _defn_label(obj: AttributeDefinition) -> str:
    unit = f" ({obj.unit_display})" if obj.unit_display else ""
    return f"{obj.label}{unit} [{obj.get_value_type_display()}]"


class ProductAttributeValueForm(forms.ModelForm[ProductAttributeValue]):
    class Meta:
        model = ProductAttributeValue
        fields = ["definition", "value"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        qs = AttributeDefinition.objects.all().order_by("name")

        product = None
        if self.instance and self.instance.pk and self.instance.product_id:
            product = self.instance.product
        elif "product" in self.initial:
            product = self.initial["product"]

        if product and product.category_id:
            assigned_ids = AttributeAssignment.objects.filter(
                category=product.category,
                scope=AttributeScope.PRODUCT,
            ).values_list("definition_id", flat=True)
            qs = qs.filter(pk__in=assigned_ids)

        definition_field = cast(
            "forms.ModelChoiceField[AttributeDefinition]",
            self.fields["definition"],
        )
        definition_field.queryset = qs
        cast("Any", definition_field).label_from_instance = _defn_label

        defn: AttributeDefinition | None = None
        if self.instance and self.instance.pk and self.instance.definition_id:
            defn = self.instance.definition
        elif self.data.get(self.add_prefix("definition")):
            with contextlib.suppress(AttributeDefinition.DoesNotExist):
                defn = AttributeDefinition.objects.get(
                    pk=self.data[self.add_prefix("definition")]
                )

        if defn:
            apply_value_widget(self.fields, defn)


class ProductAttributeValueInline(admin.TabularInline[ProductAttributeValue, Product]):
    model = ProductAttributeValue
    form = ProductAttributeValueForm
    extra = 0
    fields = ["definition", "value"]
    verbose_name = _("Product Attribute")
    verbose_name_plural = _("Product Attributes")

    def get_extra(
        self,
        request: Any,
        obj: Product | None = None,
        **kwargs: Any,
    ) -> int:
        return 0 if obj is None else 1

    def get_formset(
        self,
        request: Any,
        obj: Product | None = None,
        **kwargs: Any,
    ) -> Any:
        formset = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            original_init = formset.form.__init__

            def patched_init(self_form: Any, *args: Any, **kw: Any) -> None:
                kw.setdefault("initial", {})["product"] = obj
                original_init(self_form, *args, **kw)

            cast("Any", formset.form).__init__ = patched_init
        return formset


class ProductVariantInline(admin.TabularInline[ProductVariant, Product]):
    model = ProductVariant
    extra = 1
    fields = ["sku", "is_active"]
    show_change_link = True
    verbose_name = _("Variant")
    verbose_name_plural = _("Variants - click 'change' to add attributes & images")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin[Product]):
    form = ProductAdminForm
    list_display = [
        "name",
        "category",
        "brand",
        "product_type",
        "fulfilment_type",
        "is_active",
        "created",
    ]
    list_filter = ["product_type", "fulfilment_type", "is_active", "category"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    readonly_fields = ["created", "modified"]

    fieldsets = (
        (
            None,
            {"fields": ("name", "slug", "description")},
        ),
        (
            _("Classification"),
            {
                "fields": (
                    "category",
                    "brand",
                    "product_type",
                    "fulfilment_type",
                    "tax_class",
                )
            },
        ),
        (
            _("Status"),
            {"fields": ("is_active",)},
        ),
        (
            _("Dimensions & Extra Attributes"),
            {
                "fields": ("other_attributes",),
                "description": _(
                    "For shippable products (Shipment / Local Delivery / Store Pickup) "
                    "the Shipping Dimensions group is shown and required. "
                    "Use Extra Attributes below it for any additional key/value data."
                ),
            },
        ),
        (
            _("SEO"),
            {
                "fields": ("meta_title", "meta_description"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request: Any) -> Any:
        return super().get_queryset(request).select_related("category", "brand")

    def get_inlines(
        self,
        request: Any,
        obj: Product | None,
    ) -> list[Any]:
        if obj is None:
            return [ProductVariantInline]
        return [ProductAttributeValueInline, ProductVariantInline]


class VariantAttributeValueForm(forms.ModelForm[VariantAttributeValue]):
    class Meta:
        model = VariantAttributeValue
        fields = ["definition", "value"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        qs = AttributeDefinition.objects.all().order_by("name")

        variant = None
        if self.instance and self.instance.pk and self.instance.variant_id:
            variant = self.instance.variant
        elif "variant" in self.initial:
            variant = self.initial["variant"]

        if variant and variant.product_id:
            product = variant.product
            assigned_ids = AttributeAssignment.objects.filter(
                scope=AttributeScope.VARIANT,
                category_id=product.category_id,
            ).values_list("definition_id", flat=True)
            qs = qs.filter(pk__in=assigned_ids)

        definition_field = cast(
            "forms.ModelChoiceField[AttributeDefinition]",
            self.fields["definition"],
        )
        definition_field.queryset = qs
        cast("Any", definition_field).label_from_instance = _defn_label

        defn: AttributeDefinition | None = None
        if self.instance and self.instance.pk and self.instance.definition_id:
            defn = self.instance.definition
        elif self.data.get(self.add_prefix("definition")):
            with contextlib.suppress(AttributeDefinition.DoesNotExist):
                defn = AttributeDefinition.objects.get(
                    pk=self.data[self.add_prefix("definition")]
                )

        if defn:
            apply_value_widget(self.fields, defn)


class VariantAttributeValueInline(
    admin.TabularInline[VariantAttributeValue, ProductVariant]
):
    model = VariantAttributeValue
    form = VariantAttributeValueForm
    extra = 0
    fields = ["definition", "value"]
    verbose_name = _("Variant Attribute")
    verbose_name_plural = _("Variant Attributes")

    def get_extra(
        self,
        request: Any,
        obj: ProductVariant | None = None,
        **kwargs: Any,
    ) -> int:
        return 0 if obj is None else 1

    def get_formset(
        self,
        request: Any,
        obj: ProductVariant | None = None,
        **kwargs: Any,
    ) -> Any:
        formset = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            original_init = formset.form.__init__

            def patched_init(self_form: Any, *args: Any, **kw: Any) -> None:
                kw.setdefault("initial", {})["variant"] = obj
                original_init(self_form, *args, **kw)

            cast("Any", formset.form).__init__ = patched_init
        return formset


class ProductImageInline(admin.TabularInline[ProductImage, ProductVariant]):
    model = ProductImage
    extra = 1
    fields = ["image", "alt_text", "is_primary", "display_order"]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin[ProductVariant]):
    form = ProductVariantAdminForm
    list_display = ["sku", "product", "is_active", "created"]
    list_filter = ["is_active", "product__category"]
    search_fields = ["sku", "product__name"]
    readonly_fields = ["created", "modified"]
    autocomplete_fields = ["product"]

    fieldsets = (
        (
            None,
            {"fields": ("product", "sku", "is_active")},
        ),
        (
            _("Extra Attributes"),
            {
                "fields": ("other_attributes",),
                "classes": ("collapse",),
                "description": _(
                    "Free-form key/value pairs for this variant. "
                    "These supplement the structured attribute system."
                ),
            },
        ),
        (
            _("Timestamps"),
            {"fields": ("created", "modified"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request: Any) -> Any:
        return (
            super().get_queryset(request).select_related("product", "product__category")
        )

    def get_inlines(
        self,
        request: Any,
        obj: ProductVariant | None,
    ) -> list[Any]:
        if obj is None:
            return []
        return [VariantAttributeValueInline, ProductImageInline]
