from django import forms
from django.utils.translation import gettext_lazy as _

from .models import CustomerAddress
from .models import CustomerProfile


class CustomerProfileForm(forms.ModelForm[CustomerProfile]):
    """
    Used on the customer-facing profile edit page.
    Excludes: user (set by view), avatar (separate upload form),
              accepts_marketing (separate preference form).
    """

    class Meta:
        model = CustomerProfile
        fields = ["first_name", "last_name", "phone_number", "gender", "date_of_birth"]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d",
            ),
        }
        labels = {
            "date_of_birth": _("Date of Birth"),
        }


class MarketingPreferenceForm(forms.ModelForm[CustomerProfile]):
    class Meta:
        model = CustomerProfile
        fields = ["accepts_marketing"]
        labels = {
            "accepts_marketing": _(
                "I agree to receive promotional emails and notifications"
            )
        }


class UserAddressForm(forms.ModelForm[CustomerAddress]):
    class Meta:
        model = CustomerAddress
        fields = [
            "full_name",
            "contact_number",
            "address_type",
            "address_line1",
            "address_line2",
            "landmark",
            "city",
            "state",
            "country",
            "pincode",
            "is_default",
        ]
        widgets = {
            "address_line2": forms.TextInput(attrs={"placeholder": _("Optional")}),
            "landmark": forms.TextInput(attrs={"placeholder": _("Optional")}),
        }
