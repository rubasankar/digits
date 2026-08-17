"""
Accounts app -- authentication only.

Responsibility
--------------
This app owns exactly one thing: the UserAccount model that Django uses
for authentication.  Nothing else lives here.

Why keep it separate from 'users'?
-----------------------------------
Django requires AUTH_USER_MODEL to point to a single, stable model.
Keeping it in its own small app means:
  - The auth model never gets tangled with business-logic profile fields.
  - Migrations for profile/address changes don't touch the auth table.
  - apps.accounts can be swapped or extended without touching apps.users.

Three types of people on this platform
---------------------------------------
All three share this same UserAccount for authentication.
Their roles and extended data live in separate apps:

  1. End Customer  -- shops the store; has
                    apps.customers.CustomerProfile + saved addresses
  2. Store Staff   -- limited access to orders/inventory; has apps.staff.StaffProfile
  3. Store Admin   -- full management access (is_staff=True on UserAccount)

Role differentiation is done via:s
  - UserAccount.is_staff / is_superuser  -  Django admin access
  - Django Groups + Permissions          -  granular staff permissions
  - apps.staff.StaffProfile              -  staff operational metadata
  - apps.customers.CustomerProfile       -  customer personal data
"""

from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from .managers import UserManager


class UserAccount(UUIDModel, AbstractUser, TimeStampedModel):
    """
    The single authentication identity for every person on the platform.
    """

    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    username = None  # type: ignore[assignment]

    email = models.EmailField(
        _("Email Address"),
        unique=True,
        help_text=_(
            "Used as the login identifier. Must be unique across the platform."
        ),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        verbose_name = _("User Account")
        verbose_name_plural = _("User Accounts")
        ordering = ["-date_joined"]

    @property
    def is_customer(self) -> bool:
        """True if this account has a customer profile (i.e. is a shopper)."""
        return hasattr(self, "customer_profile")

    @property
    def is_store_staff(self) -> bool:
        """True if this account has a staff profile (i.e. is an employee)."""
        return hasattr(self, "staff_profile")

    def __str__(self) -> str:
        return self.email

    def __repr__(self) -> str:
        return f"<UserAccount id={self.id} email={self.email!r} staff={self.is_staff}>"
