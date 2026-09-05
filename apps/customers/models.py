from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel
from phonenumber_field.modelfields import PhoneNumberField

from core.enums import AddressChoices
from core.models import AddressBaseModel

from .enums import GenderChoices

User = get_user_model()


class CustomerProfile(UUIDModel, TimeStampedModel):
    user = models.OneToOneField(
        User,
        verbose_name=_("User Account"),
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    first_name = models.CharField(_("First Name"), max_length=100)
    last_name = models.CharField(_("Last Name"), max_length=100, blank=True)
    date_of_birth = models.DateField(
        _("Date of Birth"),
        null=True,
        blank=True,
        help_text=_("Used for age-gated products and birthday promotions."),
    )
    gender = models.CharField(
        _("Gender"),
        max_length=1,
        choices=GenderChoices,
        default=GenderChoices.PREFER_NOT_TO_SAY,
    )
    avatar = models.ImageField(
        _("Avatar"),
        upload_to="avatars/customers/",
        blank=True,
    )
    accepts_marketing = models.BooleanField(
        _("Accepts Marketing"),
        default=False,
        help_text=_("Customer opted in to promotional emails and notifications."),
    )

    class Meta:
        verbose_name = _("Customer Profile")
        verbose_name_plural = _("Customer Profiles")
        ordering = ["first_name", "last_name"]

    @property
    def full_name(self) -> str:

        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return self.full_name or self.user.email

    def __repr__(self) -> str:
        return f"<CustomerProfile id={self.id} user={self.user}>"


class CustomerAddress(UUIDModel, TimeStampedModel, AddressBaseModel):
    customer = models.ForeignKey(
        CustomerProfile,
        verbose_name=_("Customer"),
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        _("Address Type"),
        max_length=4,
        choices=AddressChoices,
        default=AddressChoices.BOTH,
    )
    full_name = models.CharField(
        _("Recipient Full Name"),
        max_length=150,
        help_text=_("Name printed on the shipping label."),
    )
    contact_number = PhoneNumberField(
        _("Contact Number"),
        help_text=_("Phone number for the delivery courier."),
    )
    is_default = models.BooleanField(
        _("Default Address"),
        default=False,
        help_text=_(
            "Preferred address for this type. "
            "Only one default is allowed per address_type per user."
        ),
    )

    class Meta:
        verbose_name = _("Customer Address")
        verbose_name_plural = _("Customer Addresses")
        ordering = ["-is_default", "-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "address_type"],
                condition=models.Q(is_default=True),
                name="unique_default_address_per_customer_type",
            )
        ]

    def __str__(self) -> str:
        default_tag = " (default)" if self.is_default else ""
        return f"{self.full_name} -- {self.city}, {self.country}{default_tag}"

    def __repr__(self) -> str:
        return (
            f"<UserAddress id={self.id} customer={self.customer} "
            f"type={self.address_type} default={self.is_default}>"
        )
