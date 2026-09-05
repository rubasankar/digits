from __future__ import annotations

from allauth.account.forms import SignupForm
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from unfold.forms import UserChangeForm
from unfold.forms import UserCreationForm

from .models import UserAccount


class UserAdminChangeForm(UserChangeForm):  # type: ignore[misc]
    class Meta(UserChangeForm.Meta):  # type: ignore[misc]
        model = UserAccount
        field_classes = {"email": EmailField}


class UserAdminCreationForm(UserCreationForm):  # type: ignore[misc]
    class Meta(UserCreationForm.Meta):  # type: ignore[misc]
        model = UserAccount
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):  # type: ignore[misc]
    """Form rendered on the sign-up screen."""


class UserSocialSignupForm(SignupForm):  # type: ignore[misc]
    """Form for accounts created via social login."""
