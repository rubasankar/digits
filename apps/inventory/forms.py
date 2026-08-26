from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminIntegerFieldWidget
from unfold.widgets import UnfoldAdminSelectWidget
from unfold.widgets import UnfoldAdminTextareaWidget
from unfold.widgets import UnfoldAdminTextInputWidget

from apps.catalogue.models.product import ProductVariant

from .models import Warehouse


class ReceiveStockForm(forms.Form):
    variant = forms.ModelChoiceField(
        label=_("Variant"),
        queryset=ProductVariant.objects.select_related("product").order_by(
            "product__name", "sku"
        ),
        widget=UnfoldAdminSelectWidget(),
    )
    warehouse = forms.ModelChoiceField(
        label=_("Warehouse"),
        queryset=Warehouse.objects.filter(is_active=True).order_by("name"),
        widget=UnfoldAdminSelectWidget(),
    )
    quantity = forms.IntegerField(
        label=_("Quantity"),
        min_value=1,
        widget=UnfoldAdminIntegerFieldWidget(),
    )
    reference = forms.CharField(
        label=_("Reference"),
        max_length=255,
        required=False,
        widget=UnfoldAdminTextInputWidget(),
    )
    note = forms.CharField(
        label=_("Note"),
        required=False,
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3}),
    )
