from __future__ import annotations

from typing import cast

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill
from treebeard.mp_tree import MP_Node

from apps.catalogue.constants import CATEGORY_IMAGE_UPLOAD_PATH
from apps.catalogue.constants import IMAGE_FORMAT
from apps.catalogue.constants import IMAGE_THUMBNAIL_QUALITY
from apps.catalogue.constants import IMAGE_THUMBNAIL_SIZE
from apps.catalogue.managers import CategoryManager


class ProductCategory(MP_Node):  # type: ignore[misc]
    node_order_by = ["name"]

    objects = CategoryManager()

    name = models.CharField(_("Name"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=200, unique=True)
    description = models.TextField(_("Description"), blank=True)
    image = models.ImageField(
        _("Category Image"),
        upload_to=CATEGORY_IMAGE_UPLOAD_PATH,
        blank=True,
    )
    thumbnail: ImageSpecField = ImageSpecField(
        source="image",
        processors=[ResizeToFill(*IMAGE_THUMBNAIL_SIZE)],
        format=IMAGE_FORMAT,
        options={"quality": IMAGE_THUMBNAIL_QUALITY},
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Product Category")
        verbose_name_plural = _("Product Categories")

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<ProductCategory id={self.pk} name={self.name!r} depth={self.depth}>"

    def get_breadcrumb(self) -> list[ProductCategory]:
        return [*list(self.get_ancestors()), self]

    @property
    def parent(self) -> ProductCategory | None:
        return cast("ProductCategory | None", self.get_parent())

    @property
    def children(self) -> models.QuerySet[ProductCategory]:
        return cast("models.QuerySet[ProductCategory]", self.get_children())
