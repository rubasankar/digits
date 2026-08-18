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

        return hasattr(self, "customer_profile")

    @property
    def is_store_staff(self) -> bool:

        return hasattr(self, "staff_profile")

    def __str__(self) -> str:
        return self.email

    def __repr__(self) -> str:
        return f"<UserAccount id={self.id} email={self.email!r} staff={self.is_staff}>"
