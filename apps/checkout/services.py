from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.customers.services import CustomerService
from apps.inventory.services import StockMovementService
from apps.orders.service import OrderService
from apps.orders.service.order import OrderLineInput
from apps.orders.service.order import PlaceOrderInput
from apps.pricing.services import PricingService
from apps.pricing.services import TaxService
from apps.promotions.services import CouponService
from apps.promotions.services import DiscountService
from core.exceptions import CheckoutAlreadyCompletedError
from core.exceptions import CheckoutError
from core.exceptions import CheckoutSessionExpiredError
from core.exceptions import EmptyCartError
from core.exceptions import InsufficientStockError
from core.exceptions import NoPriceFoundError

from .enums import CheckoutStep
from .enums import SessionStatus
from .models import CheckoutSession

if TYPE_CHECKING:
    from uuid import UUID

    from apps.customers.models import CustomerAddress
    from apps.customers.models import CustomerProfile
    from apps.orders.models import Order
    from apps.pricing.models import Currency
    from apps.shopping.models import Cart
    from apps.shopping.models import CartItem


# Result containers


@dataclass(frozen=True)
class PlaceOrderResult:
    """Returned by CheckoutService.place_order()."""

    order: Order
    session: CheckoutSession


# CheckoutService


class CheckoutService:
    # Session lifecycle

    @classmethod
    @transaction.atomic
    def start(
        cls,
        cart: Cart,
        *,
        customer: CustomerProfile | None = None,
        ttl_hours: int = 24,
    ) -> CheckoutSession:
        # Guard: cart must have items.
        if not cart.items.exists():
            raise EmptyCartError

        # Guard: don't create a second session for a cart that's already completed.
        existing = CheckoutSession.objects.filter(cart=cart).first()
        if existing is not None:
            if existing.status == SessionStatus.COMPLETED:
                raise CheckoutAlreadyCompletedError
            # Reuse the existing active session rather than creating a duplicate.
            return existing

        expires_at = timezone.now() + timedelta(hours=ttl_hours)

        session = CheckoutSession(
            cart=cart,
            customer=customer,
            currency=cart.currency,
            coupon_code=cart.coupon_code,
            status=SessionStatus.ACTIVE,
            step=CheckoutStep.ADDRESS,
            expires_at=expires_at,
        )
        session.save()
        return session

    @classmethod
    @transaction.atomic
    def set_address(
        cls,
        session: CheckoutSession,
        *,
        shipping_address: CustomerAddress,
        billing_address: CustomerAddress | None = None,
    ) -> CheckoutSession:
        cls._assert_mutable(session)
        session.shipping_address = shipping_address
        session.billing_address = billing_address or shipping_address
        session.step = CheckoutStep.SHIPPING
        session.save(
            update_fields=["shipping_address", "billing_address", "step", "modified"]
        )
        return session

    @classmethod
    @transaction.atomic
    def set_shipping(
        cls,
        session: CheckoutSession,
        *,
        shipping_method: str,
        shipping_cost: Decimal,
    ) -> CheckoutSession:
        """Record shipping method and cost; advance to PAYMENT step."""
        cls._assert_mutable(session)
        if shipping_cost < Decimal("0"):
            raise ValidationError(
                {"shipping_cost": _("Shipping cost cannot be negative.")}
            )

        session.shipping_method = shipping_method
        session.shipping_cost = shipping_cost
        session.step = CheckoutStep.PAYMENT
        session.save(
            update_fields=["shipping_method", "shipping_cost", "step", "modified"]
        )
        return session

    @classmethod
    @transaction.atomic
    def apply_coupon(
        cls,
        session: CheckoutSession,
        code: str,
        *,
        customer: CustomerProfile,
    ) -> CheckoutSession:
        """
        Validate and store a coupon code on the session.

        Raises a ``CouponError`` subclass when the code is invalid.
        """

        cls._assert_mutable(session)

        # Calculate current sub-total for minimum-cart-value check.
        cart_sub_total = cls._calculate_sub_total(session.cart)

        # validate() raises CouponError on failure - let it propagate.
        CouponService.validate(
            code,
            customer=customer,
            cart_sub_total=cart_sub_total,
        )

        session.coupon_code = code.strip().upper()
        session.save(update_fields=["coupon_code", "modified"])
        return session

    @classmethod
    @transaction.atomic
    def remove_coupon(cls, session: CheckoutSession) -> CheckoutSession:
        """Clear the coupon code from the session."""
        cls._assert_mutable(session)
        session.coupon_code = ""
        session.save(update_fields=["coupon_code", "modified"])
        return session

    @classmethod
    @transaction.atomic
    def abandon(cls, session: CheckoutSession) -> CheckoutSession:
        """Mark the session as ABANDONED (customer left checkout)."""
        if session.status in {SessionStatus.COMPLETED, SessionStatus.ABANDONED}:
            return session
        session.status = SessionStatus.ABANDONED
        session.save(update_fields=["status", "modified"])
        return session

    # Place order (the full pipeline)

    @classmethod
    @transaction.atomic
    def place_order(cls, session: CheckoutSession) -> PlaceOrderResult:

        #  Step 1: guard session state
        cls._assert_mutable(session)
        cls._assert_not_expired(session)

        #  Step 2: validate cart
        cart = session.cart
        cart_items = list(
            cart.items.select_related(
                "variant__product__category",
                "variant__product__tax_class",
            ).all()
        )
        if not cart_items:
            raise EmptyCartError
        cls._validate_cart_items(cart_items)

        #  Step 3: address snapshots
        shipping_address = session.shipping_address
        billing_address = session.billing_address
        if shipping_address is None or billing_address is None:
            raise ValidationError(
                _("Shipping and billing addresses must be set before placing an order.")
            )

        shipping_snap = CustomerService.snapshot_address(shipping_address)
        billing_snap = CustomerService.snapshot_address(billing_address)

        #  Step 4: currency
        currency = session.currency or PricingService.get_default_currency()

        #  Step 5: resolve prices, warehouses, tax per line
        lines = cls._resolve_order_lines(
            cart_items,
            currency,
            country=shipping_snap.get("country", ""),
            state=shipping_snap.get("state", ""),
        )

        #  Step 6 & 7: coupon + discount
        coupon = None
        discount_amount = Decimal("0.00")

        if session.coupon_code and session.customer:
            cart_sub_total = sum(
                (line.unit_price * line.quantity for line in lines),
                Decimal("0.00"),
            )
            # Re-validate at placement time
            # (things may have changed since apply_coupon).
            coupon = CouponService.validate(
                session.coupon_code,
                customer=session.customer,
                cart_sub_total=cart_sub_total,
            )
            discount_amount = DiscountService.calculate(
                coupon.discount,
                cart_sub_total=cart_sub_total,
                shipping_cost=session.shipping_cost,
                cart_items=cart_items,
            )

        #  Step 8: create order via OrderService
        session.status = SessionStatus.PROCESSING
        session.save(update_fields=["status", "modified"])

        order = OrderService.place_order(
            PlaceOrderInput(
                customer=session.customer or _get_customer_from_cart(cart),
                currency=currency,
                shipping_address_snapshot=shipping_snap,
                billing_address_snapshot=billing_snap,
                lines=lines,
                shipping_cost=session.shipping_cost,
                discount_amount=discount_amount,
                coupon_code=session.coupon_code,
                notes="",
            )
        )

        #  Step 9: record coupon redemption
        if coupon is not None and session.customer:
            CouponService.redeem(
                coupon,
                customer=session.customer,
                order=order,
            )

        #  Step 10: complete session
        session.status = SessionStatus.COMPLETED
        session.order = order
        session.save(update_fields=["status", "order", "modified"])

        #  Step 11: archive the cart
        cart.coupon_code = ""
        cart.save(update_fields=["coupon_code", "modified"])

        return PlaceOrderResult(order=order, session=session)

    # Internal helpers

    @classmethod
    def _assert_mutable(cls, session: CheckoutSession) -> None:
        if session.status == SessionStatus.COMPLETED:
            raise CheckoutAlreadyCompletedError
        if session.status == SessionStatus.ABANDONED:
            raise CheckoutError(str(_("This checkout session has been abandoned.")))

    @classmethod
    def _validate_cart_items(cls, cart_items: list[CartItem]) -> None:
        """Raise when any line references an inactive variant or product."""
        for ci in cart_items:
            product = ci.variant.product
            if not ci.variant.is_active or not product.is_active:
                raise ValidationError(
                    _("%(name)s is no longer available.") % {"name": product.name}
                )

    @classmethod
    def _resolve_order_lines(
        cls,
        cart_items: list[CartItem],
        currency: Currency,
        *,
        country: str,
        state: str,
    ) -> list[OrderLineInput]:
        """Resolve price, warehouse and tax rate for every cart line."""
        lines: list[OrderLineInput] = []

        for ci in cart_items:
            variant = ci.variant

            # 5a. Price
            try:
                resolved_price = PricingService.get_current_price(variant, currency)
            except NoPriceFoundError as err:
                raise NoPriceFoundError(
                    sku=variant.sku, currency_code=currency.code
                ) from err

            # 5b. Warehouse selection
            warehouse = StockMovementService.select_warehouse(variant, ci.quantity)
            if warehouse is None:
                raise InsufficientStockError(
                    sku=variant.sku,
                    requested=ci.quantity,
                    available=StockMovementService.get_available_quantity(variant),
                )

            # 5c. Tax rate
            product = variant.product
            tax_class_id: UUID | None = product.tax_class_id or None
            if tax_class_id:
                _, tax_rate = TaxService.calculate_tax_amount(
                    pre_tax_amount=resolved_price.amount * ci.quantity,
                    tax_class_id=tax_class_id,
                    country=country,
                    state=state,
                )
            else:
                tax_rate = Decimal("0.00")

            lines.append(
                OrderLineInput(
                    variant=variant,
                    quantity=ci.quantity,
                    unit_price=resolved_price.amount,
                    tax_rate=tax_rate,
                    warehouse=warehouse,
                )
            )

        return lines

    @classmethod
    def _assert_not_expired(cls, session: CheckoutSession) -> None:
        if session.expires_at and timezone.now() > session.expires_at:
            session.status = SessionStatus.ABANDONED
            session.save(update_fields=["status", "modified"])
            raise CheckoutSessionExpiredError

    @classmethod
    def _calculate_sub_total(cls, cart: Cart) -> Decimal:
        """Sum unit_price_at_add * quantity for all items in the cart."""
        total = Decimal("0.00")
        for item in cart.items.all():
            if item.unit_price_at_add is not None:
                total += item.unit_price_at_add * item.quantity
        return total


# Module-level helper (avoids circular import inside the method)


def _get_customer_from_cart(cart: Cart) -> CustomerProfile:
    if cart.customer is not None:
        return cart.customer

    raise ValidationError(_("A customer account is required to complete checkout."))
