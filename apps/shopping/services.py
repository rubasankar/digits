from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.inventory.models import Stock
from core.exceptions import NotFoundError

from .enums import CartType
from .models import Cart
from .models import CartItem
from .models import Wishlist
from .models import WishlistItem

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID

    from apps.catalogue.models.product import ProductVariant
    from apps.customers.models import CustomerProfile


# CartService


class CartService:
    """
    All cart mutation logic in one place.

    Guest carts are identified by ``session_key`` (Django session key).
    Authenticated carts are identified by ``CustomerProfile``.

    Only ONE ACTIVE cart is allowed per customer / session (enforced by the
    DB UniqueConstraint).  BUY_NOW carts follow the same rule.
    """

    # Get-or-create

    @classmethod
    @transaction.atomic
    def get_or_create_for_customer(
        cls,
        customer: CustomerProfile,
        *,
        cart_type: str = CartType.ACTIVE,
        currency_id: UUID | None = None,
    ) -> tuple[Cart, bool]:
        """Return the customer's cart of the given type, creating it if absent."""
        cart, created = Cart.objects.get_or_create(
            customer=customer,
            cart_type=cart_type,
            defaults={"currency_id": currency_id},
        )
        return cart, created

    @classmethod
    @transaction.atomic
    def get_or_create_for_session(
        cls,
        session_key: str,
        *,
        cart_type: str = CartType.ACTIVE,
        currency_id: UUID | None = None,
    ) -> tuple[Cart, bool]:
        """Return a guest cart for the given session key, creating it if absent."""
        if not session_key:
            raise ValidationError(_("A session key is required for guest carts."))
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            customer=None,
            cart_type=cart_type,
            defaults={"currency_id": currency_id},
        )
        return cart, created

    # Item mutations

    @classmethod
    @transaction.atomic
    def add_item(
        cls,
        cart: Cart,
        variant: ProductVariant,
        quantity: int = 1,
        *,
        unit_price: Decimal | None = None,
    ) -> CartItem:
        """
        Add *quantity* units of *variant* to *cart*.

        If the variant is already in the cart, quantities are combined.
        ``unit_price`` is the current storefront price - stored to detect
        price changes before checkout.

        Raises ``ValidationError`` when the cart type is MERGED (archived carts
        cannot be modified).
        """
        cls._assert_cart_mutable(cart)

        existing = CartItem.objects.filter(cart=cart, variant=variant).first()
        if existing is not None:
            new_qty = existing.quantity + quantity
            cls._validate_quantity(variant, new_qty)
            existing.quantity = new_qty
            if unit_price is not None:
                existing.unit_price_at_add = unit_price
            existing.save(update_fields=["quantity", "unit_price_at_add", "modified"])
            return existing

        cls._validate_quantity(variant, quantity)
        item = CartItem(
            cart=cart,
            variant=variant,
            quantity=quantity,
            unit_price_at_add=unit_price,
        )
        item.full_clean()
        item.save()
        return item

    @classmethod
    @transaction.atomic
    def update_quantity(
        cls,
        cart: Cart,
        variant: ProductVariant,
        quantity: int,
    ) -> CartItem:
        """Set the quantity of *variant* in *cart* to an exact value."""
        cls._assert_cart_mutable(cart)

        if quantity <= 0:
            cls.remove_item(cart, variant)
            # Return a sentinel; callers should check ``cart.items`` afterwards.
            raise ValidationError(_("Use remove_item() to set quantity to zero."))

        try:
            item = CartItem.objects.get(cart=cart, variant=variant)
        except CartItem.DoesNotExist as err:
            raise NotFoundError(str(_("Variant is not in this cart."))) from err

        cls._validate_quantity(variant, quantity)
        item.quantity = quantity
        item.save(update_fields=["quantity", "modified"])
        return item

    @classmethod
    @transaction.atomic
    def remove_item(
        cls,
        cart: Cart,
        variant: ProductVariant,
    ) -> None:
        """Remove a variant from the cart (no-op if not present)."""
        cls._assert_cart_mutable(cart)
        CartItem.objects.filter(cart=cart, variant=variant).delete()

    @classmethod
    @transaction.atomic
    def clear(cls, cart: Cart) -> int:
        """Remove all items from *cart*. Returns the number of items deleted."""
        cls._assert_cart_mutable(cart)
        count, _ = cart.items.all().delete()
        return count

    @classmethod
    @transaction.atomic
    def apply_coupon(cls, cart: Cart, code: str) -> Cart:
        """
        Store a coupon code on the cart.

        Coupon validity is NOT checked here - that happens in CheckoutService
        when the order is placed.  This just records the customer's intent.
        """
        cls._assert_cart_mutable(cart)
        cart.coupon_code = code.strip().upper()
        cart.save(update_fields=["coupon_code", "modified"])
        return cart

    @classmethod
    @transaction.atomic
    def remove_coupon(cls, cart: Cart) -> Cart:
        """Clear any applied coupon code from the cart."""
        cls._assert_cart_mutable(cart)
        cart.coupon_code = ""
        cart.save(update_fields=["coupon_code", "modified"])
        return cart

    # Internal helpers

    @classmethod
    def _assert_cart_mutable(cls, cart: Cart) -> None:
        if cart.cart_type == CartType.MERGED:
            raise ValidationError(
                _("This cart has been merged and can no longer be modified.")
            )

    @classmethod
    def _validate_quantity(
        cls,
        variant: ProductVariant,
        quantity: int,
    ) -> None:
        """
        Enforce minimum / maximum order quantity limits from stock settings.

        We look at the aggregate available stock across all warehouses to
        avoid blocking the cart add when stock exists elsewhere.
        """
        if quantity < 1:
            raise ValidationError(_("Quantity must be at least 1."))

        # Aggregate constraints across all stock rows for this variant.
        stocks = Stock.objects.filter(variant=variant)
        if not stocks.exists():
            # No stock rows yet - don't block. Service layer will catch it.
            return

        min_qty = max(s.minimum_order_qty for s in stocks)
        if quantity < min_qty:
            raise ValidationError(
                _("Minimum order quantity for this item is %(min)s.") % {"min": min_qty}
            )

        max_qtys = [s.maximum_order_qty for s in stocks if s.maximum_order_qty > 0]
        if max_qtys:
            max_qty = min(max_qtys)
            if quantity > max_qty:
                raise ValidationError(
                    _("Maximum order quantity for this item is %(max)s.")
                    % {"max": max_qty}
                )


# CartMergeService


class CartMergeService:
    """
    Merges a guest cart into a customer cart on login.

    Implements the algorithm documented in ``Cart`` model docstring.
    """

    @classmethod
    @transaction.atomic
    def merge(
        cls,
        *,
        guest_cart: Cart,
        customer: CustomerProfile,
    ) -> Cart:
        """
        Merge *guest_cart* into the customer's ACTIVE cart.

        Returns the surviving (customer) cart.

        Steps
        -----
        1. Find the customer's ACTIVE cart.
           If none exists, simply reassign the guest cart to the customer.
        2. For each CartItem in the guest cart:
           a. If the variant is already in the customer cart, add quantities
              (capped at Stock.maximum_order_qty when a limit exists).
           b. Otherwise, move the CartItem to the customer cart.
        3. Carry over the coupon code if the customer cart has none.
        4. Archive the guest cart (cart_type=MERGED, merged_into=customer_cart).
        """
        if guest_cart.cart_type == CartType.MERGED:
            raise ValidationError(_("This guest cart has already been merged."))

        # Case 1: customer has no ACTIVE cart - just reassign.
        customer_cart = Cart.objects.filter(
            customer=customer,
            cart_type=CartType.ACTIVE,
        ).first()

        if customer_cart is None:
            guest_cart.customer = customer
            guest_cart.session_key = ""
            guest_cart.save(update_fields=["customer", "session_key", "modified"])
            return guest_cart

        # Case 2: merge items.
        guest_items = list(guest_cart.items.select_related("variant").all())

        for guest_item in guest_items:
            existing = CartItem.objects.filter(
                cart=customer_cart,
                variant=guest_item.variant,
            ).first()

            if existing is not None:
                # Combine quantities, respecting stock limits.
                new_qty = existing.quantity + guest_item.quantity
                new_qty = cls._cap_quantity(guest_item.variant, new_qty)
                existing.quantity = new_qty
                # Refresh price to the more recent of the two.
                if (
                    guest_item.unit_price_at_add is not None
                    and existing.unit_price_at_add != guest_item.unit_price_at_add
                ):
                    existing.unit_price_at_add = guest_item.unit_price_at_add
                existing.save(
                    update_fields=["quantity", "unit_price_at_add", "modified"]
                )
            else:
                # Move the item to the customer cart.
                guest_item.cart = customer_cart
                guest_item.save(update_fields=["cart"])

        # Carry over coupon if the customer cart has none.
        if not customer_cart.coupon_code and guest_cart.coupon_code:
            customer_cart.coupon_code = guest_cart.coupon_code
            customer_cart.save(update_fields=["coupon_code", "modified"])

        # Archive the guest cart.
        guest_cart.cart_type = CartType.MERGED
        guest_cart.merged_into = customer_cart
        guest_cart.save(update_fields=["cart_type", "merged_into", "modified"])

        return customer_cart

    @classmethod
    def _cap_quantity(cls, variant: ProductVariant, quantity: int) -> int:
        """Cap *quantity* at the variant's maximum_order_qty if set."""

        max_qtys = list(
            Stock.objects.filter(
                variant=variant,
                maximum_order_qty__gt=0,
            ).values_list("maximum_order_qty", flat=True)
        )
        if max_qtys:
            return min(quantity, *max_qtys)
        return quantity


# WishlistService


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
        """Add *variant* to the customer's wishlist (idempotent)."""
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
        """Remove *variant* from the customer's wishlist (no-op if absent)."""
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
        """
        Remove *variant* from the wishlist and add it to the customer's ACTIVE cart.

        Returns the resulting CartItem.
        """
        cart, _ = CartService.get_or_create_for_customer(customer)
        item = CartService.add_item(cart, variant, quantity=1, unit_price=unit_price)
        cls.remove_from_wishlist(customer, variant)
        return item
