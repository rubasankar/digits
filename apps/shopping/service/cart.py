from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.customers.models import CustomerProfile
from apps.inventory.models import Stock
from apps.pricing.services import PricingService
from apps.promotions.models import Coupon
from apps.shopping.enums import CartType
from apps.shopping.models import Cart
from apps.shopping.models import CartItem
from core.exceptions import NoPriceFoundError

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID

    from django.http import HttpRequest

    from apps.catalogue.models.product import ProductVariant


class CartService:
    """Cart mutation and retrieval logic for both guests and authenticated users."""

    MAX_QUANTITY = 999

    def get_or_create_cart(self, request: HttpRequest) -> Cart:
        """Resolve the active Cart for the current request."""
        if request.user.is_authenticated:
            try:
                profile: CustomerProfile = request.user.customer_profile
            except CustomerProfile.DoesNotExist:
                return self._get_or_create_session_cart(request)
            cart, _ = Cart.objects.get_or_create(
                customer=profile,
                cart_type=CartType.ACTIVE,
            )
            return cart
        return self._get_or_create_session_cart(request)

    def _get_or_create_session_cart(self, request: HttpRequest) -> Cart:
        """Return or create a guest cart keyed by the current session."""
        if not request.session.session_key:
            request.session.create()
        cart, _ = Cart.objects.get_or_create(
            session_key=request.session.session_key,
            customer=None,
            cart_type=CartType.ACTIVE,
        )
        return cart

    @transaction.atomic
    def add_item(
        self,
        cart: Cart,
        variant: ProductVariant,
        quantity: int,
    ) -> CartItem:
        """Add or increment a variant in the cart."""
        if not 1 <= quantity <= self.MAX_QUANTITY:
            msg = f"quantity must be 1-{self.MAX_QUANTITY}"
            raise ValueError(msg)
        available = (
            self.get_available_stock(variant)
            if variant.product.is_shippable
            else self.MAX_QUANTITY
        )
        existing_qty = 0
        try:
            item = CartItem.objects.select_for_update().get(cart=cart, variant=variant)
            existing_qty = item.quantity
        except CartItem.DoesNotExist:
            item = CartItem(cart=cart, variant=variant, quantity=0)

        new_qty = existing_qty + quantity
        if new_qty > available:
            msg = f"Only {available} units available; requested {new_qty} total."
            raise ValueError(msg)
        item.quantity = new_qty
        item.unit_price_at_add = self._get_current_price(variant)
        item.save()
        return item

    @transaction.atomic
    def update_item(
        self,
        cart: Cart,
        variant_id: UUID,
        quantity: int,
    ) -> CartItem:
        """Update quantity on an existing CartItem."""
        if not 1 <= quantity <= self.MAX_QUANTITY:
            msg = f"quantity must be 1-{self.MAX_QUANTITY}"
            raise ValueError(msg)
        item = CartItem.objects.select_for_update().get(
            cart=cart, variant_id=variant_id
        )
        available = (
            self.get_available_stock(item.variant)
            if item.variant.product.is_shippable
            else self.MAX_QUANTITY
        )
        if quantity > available:
            msg = f"Only {available} units available."
            raise ValueError(msg)
        item.quantity = quantity
        item.save(update_fields=["quantity", "modified"])
        return item

    @transaction.atomic
    def remove_item(self, cart: Cart, variant_id: UUID) -> None:
        """Delete a CartItem from the cart."""
        CartItem.objects.filter(cart=cart, variant_id=variant_id).delete()

    @transaction.atomic
    def apply_coupon(self, cart: Cart, code: str) -> Cart:
        """Validate and apply a coupon code to the cart."""
        now = timezone.now()
        try:
            Coupon.objects.get(
                code__iexact=code,
                is_active=True,
                valid_from__lte=now,
                valid_to__gte=now,
            )
        except Coupon.DoesNotExist as err:
            msg = f"Coupon code '{code}' is invalid or expired."
            raise ValueError(msg) from err
        cart.coupon_code = code
        cart.save(update_fields=["coupon_code", "modified"])
        return cart

    def get_cart_item_count(self, request: HttpRequest) -> int:
        """Return total item count across all CartItems for the active cart."""
        try:
            cart = self.get_or_create_cart(request)
            result = cart.items.aggregate(total=Sum("quantity"))
            return int(result["total"] or 0)
        except Exception:  # noqa: BLE001
            return 0

    @staticmethod
    def get_available_stock(variant: ProductVariant) -> int:
        """Return total available stock for a variant across active warehouses."""
        result = Stock.objects.filter(
            variant=variant,
            warehouse__is_active=True,
        ).aggregate(total=Sum("quantity") - Sum("reserved_quantity"))
        return max(0, int(result["total"] or 0))

    def _get_current_price(self, variant: ProductVariant) -> Decimal | None:
        """
        Return the current price (SALE if active, else BASE) for a variant in
        the storefront's default currency, via PricingService -- the same
        resolution checkout uses, so a cart snapshot never disagrees with the
        price the customer is actually charged.
        """
        try:
            currency = PricingService.get_default_currency()
            resolved = PricingService.get_current_price(variant, currency)
        except NoPriceFoundError:
            return None
        return resolved.amount
