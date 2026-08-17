from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _

from .models import UserAccount


class UserAdminChangeForm(admin_forms.UserChangeForm[UserAccount]):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = UserAccount
        field_classes = {"email": EmailField}


class UserAdminCreationForm(admin_forms.AdminUserCreationForm[UserAccount]):
    """Form for User Creation in the Admin Area."""

    class Meta(admin_forms.UserCreationForm.Meta):
        model = UserAccount
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_messages = {
            "email": {"unique": _("This email has already been taken.")},
        }


class UserSignupForm(SignupForm):  # type: ignore[misc]
    """
    Form rendered on the sign-up screen.
    Login is email-only; no username field needed.
    """


class UserSocialSignupForm(SocialSignupForm):  # type: ignore[misc]
    """Form for accounts created via social login."""
