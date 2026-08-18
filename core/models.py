from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel


class AddressBaseModel(models.Model):
    """
    Reusable postal address fields.

    Inherit as abstract in any model that needs a physical address:
    customers.CustomerAddress, inventory.Warehouse.

    `country` uses django-countries CountryField which stores a 2-char
    ISO 3166-1 alpha-2 code (e.g. "GB", "US", "IN") and renders as a
    select widget with country names in the admin and forms.
    """

    address_line1 = models.CharField(_("Address Line 1"), max_length=255)
    address_line2 = models.CharField(_("Address Line 2"), max_length=255, blank=True)
    landmark = models.CharField(_("Landmark"), max_length=100, blank=True)
    city = models.CharField(_("City / District"), max_length=100)
    state = models.CharField(_("State / Province"), max_length=100)
    country = CountryField(_("Country"))
    pincode = models.CharField(_("Pin / Zip Code"), max_length=20)

    class Meta:
        abstract = True


class BaseModel(UUIDModel, TimeStampedModel):
    """
    Base for any entity with a name, URL slug, and description.

    Inherits:
      - UUID primary key    (from UUIDModel)
      - created / modified  (from TimeStampedModel)

    Adds:
      - name        : human-readable display name
      - slug        : URL-safe identifier (auto-generated from name on first save)
      - description : optional long description
    """

    name = models.CharField(_("Name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=200, unique=True)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        abstract = True

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
