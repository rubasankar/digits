from __future__ import annotations

from typing import cast

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.catalogue.models.category import ProductCategory


class CategoryService:
    # Creation
    @classmethod
    @transaction.atomic
    def create_root(
        cls,
        *,
        name: str,
        slug: str | None = None,
        description: str = "",
        is_active: bool = True,
    ) -> ProductCategory:
        resolved_slug = slug or slugify(name)
        cls._assert_slug_available(resolved_slug)

        return cast(
            "ProductCategory",
            ProductCategory.objects.add_root(
                create_kwargs={
                    "name": name,
                    "slug": resolved_slug,
                    "description": description,
                    "is_active": is_active,
                },
            ),
        )

    @classmethod
    @transaction.atomic
    def create_child(
        cls,
        parent: ProductCategory,
        *,
        name: str,
        slug: str | None = None,
        description: str = "",
        is_active: bool = True,
    ) -> ProductCategory:
        resolved_slug = slug or slugify(name)
        cls._assert_slug_available(resolved_slug)

        return cast(
            "ProductCategory",
            parent.add_child(
                create_kwargs={
                    "name": name,
                    "slug": resolved_slug,
                    "description": description,
                    "is_active": is_active,
                },
            ),
        )

    # Structure
    @classmethod
    @transaction.atomic
    def move(
        cls,
        node: ProductCategory,
        target: ProductCategory,
        position: str = "sorted-child",
    ) -> None:
        if target.pk == node.pk:
            raise ValidationError(_("A category cannot be moved to itself."))
        if target.is_descendant_of(node):
            raise ValidationError(
                _("Cannot move a category into one of its own descendants.")
            )
        node.move(target, pos=position)

    # Activation
    @classmethod
    @transaction.atomic
    def set_active(
        cls,
        category: ProductCategory,
        *,
        is_active: bool,
        cascade: bool = False,
    ) -> int:
        category.is_active = is_active
        category.save(update_fields=["is_active"])
        updated = 1

        if cascade:
            updated += category.get_descendants().update(is_active=is_active)
        return updated

    # Navigation helpers
    @classmethod
    def get_breadcrumb(
        cls,
        category: ProductCategory,
    ) -> list[ProductCategory]:
        return category.get_breadcrumb()

    @classmethod
    def get_active_tree(cls) -> list[ProductCategory]:
        return list(ProductCategory.objects.active().order_by("path"))

    # Private helpers
    @classmethod
    def _assert_slug_available(cls, slug: str) -> None:
        if ProductCategory.objects.filter(slug=slug).exists():
            raise ValidationError(
                {
                    "slug": _("A category with slug '%(s)s' already exists.")
                    % {"s": slug}
                }
            )
