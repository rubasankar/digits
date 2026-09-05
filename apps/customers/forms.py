from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.widgets import UnfoldAdminSingleDateWidget
from unfold.widgets import UnfoldAdminTextInputWidget

from .models import CustomerAddress
from .models import CustomerProfile

if TYPE_CHECKING:
    import datetime

_MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MIN_AGE_YEARS = 13


class CustomerProfileForm(forms.ModelForm[CustomerProfile]):
    class Meta:
        model = CustomerProfile
        fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "avatar",
            "accepts_marketing",
        ]
        widgets = {
            "date_of_birth": UnfoldAdminSingleDateWidget(),
        }
        labels = {
            "date_of_birth": _("Date of Birth"),
            "accepts_marketing": _(
                "I agree to receive promotional emails and notifications"
            ),
        }

    def clean_avatar(self) -> object:
        """Validate avatar size (<= 5 MB) and content type (JPEG/PNG/WebP)."""
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return avatar
        # InMemoryUploadedFile / TemporaryUploadedFile both expose .size
        if hasattr(avatar, "size") and avatar.size > _MAX_AVATAR_BYTES:
            raise forms.ValidationError(_("Avatar file size must be 5 MB or less."))
        content_type = getattr(avatar, "content_type", None)
        if content_type and content_type not in _ALLOWED_AVATAR_TYPES:
            raise forms.ValidationError(_("Avatar must be a JPEG, PNG, or WebP image."))
        return avatar

    def clean_date_of_birth(self) -> datetime.date | None:
        """Validate date_of_birth is in the past and user is at least 13 years old."""
        dob: datetime.date | None = self.cleaned_data.get("date_of_birth")
        if dob is None:
            return dob
        today = timezone.now().date()
        if dob >= today:
            raise forms.ValidationError(_("Date of birth must be in the past."))
        try:
            min_dob = today.replace(year=today.year - _MIN_AGE_YEARS)
        except ValueError:
            # today is Feb 29 and (today.year - _MIN_AGE_YEARS) isn't a leap year.
            min_dob = today.replace(month=2, day=28, year=today.year - _MIN_AGE_YEARS)
        if dob > min_dob:
            raise forms.ValidationError(_("You must be at least 13 years old."))
        return dob


class MarketingPreferenceForm(forms.ModelForm[CustomerProfile]):
    class Meta:
        model = CustomerProfile
        fields = ["accepts_marketing"]
        labels = {
            "accepts_marketing": _(
                "I agree to receive promotional emails and notifications"
            )
        }


class CustomerAddressForm(forms.ModelForm[CustomerAddress]):
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
            "address_line2": UnfoldAdminTextInputWidget(
                attrs={"placeholder": _("Optional")}
            ),
            "landmark": UnfoldAdminTextInputWidget(
                attrs={"placeholder": _("Optional")}
            ),
        }
