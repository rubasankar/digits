from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from apps.shopping.enums import CartType
from apps.shopping.models import Cart
from apps.shopping.models import CartItem
from apps.shopping.models import Wishlist
from apps.shopping.models import WishlistItem
from apps.shopping.service.cart import CartService

if TYPE_CHECKING:
    from decimal import Decimal

    from apps.catalogue.models.product import ProductVariant
    from apps.customers.models import CustomerProfile


class WishlistService:
    """Manages the customer's wishlist."""

    @classmethod
    @transaction.atomic
    def get_or_create_wishlist(
        cls,
        customer: CustomerProfile,
    ) -> tuple[Wishlist, bool]:
        """Return the customer's wishlist, creating it if absent."""
        return Wishlist.objects.get_or_create(customer=customer)

    @classmethod
    @transaction.atomic
    def add_to_wishlist(
        cls,
        customer: CustomerProfile,
        variant: ProductVariant,
    ) -> WishlistItem:
        """Add variant to the customer's wishlist (idempotent)."""
        wishlist, _ = cls.get_or_create_wishlist(customer)
        item, _ = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            variant=variant,
        )
        return item

    @classmethod
    @transaction.atomic
    def remove_from_wishlist(
        cls,
        customer: CustomerProfile,
        variant: ProductVariant,
    ) -> None:
        """Remove variant from the customer's wishlist (no-op if absent)."""
        wishlist = Wishlist.objects.filter(customer=customer).first()
        if wishlist is None:
            return
        WishlistItem.objects.filter(wishlist=wishlist, variant=variant).delete()

    @classmethod
    @transaction.atomic
    def move_to_cart(
        cls,
        customer: CustomerProfile,
        variant: ProductVariant,
        *,
        unit_price: Decimal | None = None,
    ) -> CartItem:
        """Remove variant from the wishlist and add it to the customer's ACTIVE cart."""
        cart, _ = Cart.objects.get_or_create(
            customer=customer,
            cart_type=CartType.ACTIVE,
        )
        item = CartService().add_item(cart, variant, quantity=1)
        if unit_price is not None:
            item.unit_price_at_add = unit_price
            item.save(update_fields=["unit_price_at_add", "modified"])
        cls.remove_from_wishlist(customer, variant)
        return item
