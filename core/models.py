from typing import Any

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


class GlobalSettings(models.Model):
    """
    Platform-wide configuration switches.

    This is a singleton model - exactly one row must exist.
    Use GlobalSettings.get() in application code; never query directly.

    Settings here are intentionally coarse-grained. Fine-grained
    feature flags belong in a dedicated feature-flag system once the
    platform grows past MVP.
    """

    # Reviews
    auto_publish_reviews = models.BooleanField(
        _("Auto-publish Reviews"),
        default=False,
        help_text=_(
            "When True, newly submitted reviews are immediately visible on the "
            "storefront (is_published=True) without staff approval. "
            "When False, staff must publish each review manually."
        ),
    )

    class Meta:
        verbose_name = _("Global Settings")
        verbose_name_plural = _("Global Settings")

    def __str__(self) -> str:
        return "Global Settings"

    def __repr__(self) -> str:
        return f"<GlobalSettings auto_publish_reviews={self.auto_publish_reviews}>"

    # Singleton helpers

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Force pk=1 so there can only ever be one row.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        # Prevent accidental deletion of the singleton row.
        msg = "GlobalSettings cannot be deleted."
        raise RuntimeError(msg)

    @classmethod
    def get(cls) -> GlobalSettings:
        """
        Return the single GlobalSettings row, creating it with defaults if absent.

        Always use this instead of .objects.get() or .objects.first() so callers
        never have to handle the DoesNotExist case.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
