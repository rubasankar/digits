from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from treebeard.mp_tree import MP_NodeManager

from .querysets import ProductCategoryQuerySet
from .querysets import ProductQuerySet
from .querysets import ProductVariantQuerySet

if TYPE_CHECKING:
    from .models.product import Product  # noqa: F401
    from .models.product import ProductVariant


class CategoryManager(MP_NodeManager):  # type: ignore[misc]
    def get_queryset(self) -> ProductCategoryQuerySet:
        return ProductCategoryQuerySet(self.model, using=self._db)

    def active(self) -> ProductCategoryQuerySet:
        return self.get_queryset().active()

    def inactive(self) -> ProductCategoryQuerySet:
        return self.get_queryset().inactive()

    def active_roots(self) -> ProductCategoryQuerySet:
        return self.get_queryset().active().roots().order_by("name")


class ProductManager(models.Manager["Product"]):
    def get_queryset(self) -> ProductQuerySet:
        return ProductQuerySet(self.model, using=self._db)

    def active(self) -> ProductQuerySet:
        return self.get_queryset().active()

    def inactive(self) -> ProductQuerySet:
        return self.get_queryset().inactive()


class ProductVariantManager(models.Manager["ProductVariant"]):
    def get_queryset(self) -> ProductVariantQuerySet:
        return ProductVariantQuerySet(self.model, using=self._db)

    def active(self) -> ProductVariantQuerySet:
        return self.get_queryset().active()

    def inactive(self) -> ProductVariantQuerySet:
        return self.get_queryset().inactive()

    def get_by_sku(self, sku: str) -> ProductVariant:
        return self.get_queryset().by_sku(sku).get()
