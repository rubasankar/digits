from __future__ import annotations

from django.db import transaction

from apps.shopping.enums import CartType
from apps.shopping.models import Cart
from apps.shopping.models import CartItem
from apps.shopping.service.cart import CartService


class CartMergeService:
    """Merges a guest cart into a customer cart on login."""

    @transaction.atomic
    def merge(self, guest_cart: Cart, customer_cart: Cart) -> Cart:
        """
        Merge guest_cart into customer_cart.

        Shared variants: quantities are summed, capped the same way
        CartService.add_item caps a manual add -- available stock for
        shippable products, CartService.MAX_QUANTITY otherwise.
        New variants: CartItem is transferred to customer_cart.
        Coupon: guest coupon copied if customer cart has none.
        guest_cart is marked MERGED and linked to customer_cart.
        """
        guest_items = list(CartItem.objects.select_for_update().filter(cart=guest_cart))
        for guest_item in guest_items:
            try:
                customer_item = CartItem.objects.select_for_update().get(
                    cart=customer_cart,
                    variant=guest_item.variant,
                )
                available = (
                    CartService.get_available_stock(guest_item.variant)
                    if guest_item.variant.product.is_shippable
                    else CartService.MAX_QUANTITY
                )
                merged_qty = min(
                    customer_item.quantity + guest_item.quantity, available
                )
                customer_item.quantity = merged_qty
                customer_item.save(update_fields=["quantity", "modified"])
                guest_item.delete()
            except CartItem.DoesNotExist:
                guest_item.cart = customer_cart
                guest_item.save(update_fields=["cart", "modified"])

        if not customer_cart.coupon_code and guest_cart.coupon_code:
            customer_cart.coupon_code = guest_cart.coupon_code
            customer_cart.save(update_fields=["coupon_code", "modified"])

        guest_cart.cart_type = CartType.MERGED
        guest_cart.merged_into = customer_cart
        guest_cart.save(update_fields=["cart_type", "merged_into", "modified"])
        return customer_cart
