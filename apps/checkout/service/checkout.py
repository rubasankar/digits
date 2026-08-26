from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.checkout.enums import CheckoutStep
from apps.checkout.enums import SessionStatus
from apps.checkout.models import CheckoutSession
from apps.customers.service.profile import CustomerService
from apps.inventory.services import StockMovementService
from apps.orders.service import OrderService
from apps.orders.service.order import OrderLineInput
from apps.orders.service.order import PlaceOrderInput
from apps.pricing.services import PricingService
from apps.pricing.services import TaxService
from apps.promotions.services import CouponService
from apps.promotions.services import DiscountService
from apps.shipping.models import ShippingMethod
from core.exceptions import CheckoutAlreadyCompletedError
from core.exceptions import CheckoutError
from core.exceptions import CheckoutSessionExpiredError
from core.exceptions import EmptyCartError
from core.exceptions import InsufficientStockError
from core.exceptions import NoPriceFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from apps.customers.models import CustomerAddress
    from apps.customers.models import CustomerProfile
    from apps.orders.models import Order
    from apps.pricing.models import Currency
    from apps.shopping.models import Cart
    from apps.shopping.models import CartItem


class CheckoutIncompleteError(Exception):
    """Raised when checkout.complete() is called with missing required fields."""


# Result containers


@dataclass(frozen=True)
class PlaceOrderResult:
    """Returned by CheckoutService.place_order()."""

    order: Order
    session: CheckoutSession


# Step order used by build_step_context and require_checkout_step

STEP_ORDER = [
    CheckoutStep.ADDRESS,
    CheckoutStep.SHIPPING,
    CheckoutStep.PAYMENT,
    CheckoutStep.CONFIRMATION,
]

_STEP_URL_MAP: dict[str, str] = {
    CheckoutStep.ADDRESS: "checkout:address",
    CheckoutStep.SHIPPING: "checkout:shipping",
    CheckoutStep.PAYMENT: "checkout:payment",
    CheckoutStep.CONFIRMATION: "checkout:review",
}


def build_step_context(session: CheckoutSession) -> dict[str, object]:
    """Return checkout_steps list and checkout_session for template step indicator."""
    current_idx = STEP_ORDER.index(CheckoutStep(session.step))
    steps: list[dict[str, str]] = []
    for i, step in enumerate(STEP_ORDER):
        if i < current_idx:
            state = "done"
        elif i == current_idx:
            state = "current"
        else:
            state = "upcoming"
        steps.append({"name": step, "url": _STEP_URL_MAP[step], "state": state})
    return {"checkout_steps": steps, "checkout_session": session}


# CheckoutService


class CheckoutService:
    SESSION_TTL_MINUTES = 30

    # Session lifecycle

    @classmethod
    @transaction.atomic
    def get_or_create_session(cls, cart: Cart) -> CheckoutSession:
        """Create or resume the active CheckoutSession for this cart (design API)."""
        session, _ = CheckoutSession.objects.get_or_create(
            cart=cart,
            status=SessionStatus.ACTIVE,
            defaults={
                "customer": cart.customer,
                "expires_at": timezone.now()
                + timedelta(minutes=cls.SESSION_TTL_MINUTES),
            },
        )
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
        """Set shipping and billing addresses; advance step to SHIPPING."""
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
    def set_shipping_method(
        cls,
        session: CheckoutSession,
        method_name: str,
        cost: Decimal,
    ) -> CheckoutSession:
        """Record selected shipping method; advance step to PAYMENT (design API)."""
        cls._assert_mutable(session)
        if cost < Decimal("0"):
            raise ValidationError(
                {"shipping_cost": _("Shipping cost cannot be negative.")}
            )
        session.shipping_method = method_name
        session.shipping_cost = cost
        session.step = CheckoutStep.PAYMENT
        session.save(
            update_fields=["shipping_method", "shipping_cost", "step", "modified"]
        )
        return session

    @classmethod
    @transaction.atomic
    def set_billing_address(
        cls,
        session: CheckoutSession,
        *,
        billing_address: CustomerAddress,
    ) -> CheckoutSession:
        """Record the billing address for payment; advance to CONFIRMATION step."""
        cls._assert_mutable(session)
        session.billing_address = billing_address
        session.status = SessionStatus.PROCESSING
        session.step = CheckoutStep.CONFIRMATION
        session.save(update_fields=["billing_address", "status", "step", "modified"])
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
        """Validate and store a coupon code on the session."""
        cls._assert_mutable(session)

        cart_sub_total = cls._calculate_sub_total(session.cart)

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
        """Mark the session as ABANDONED."""
        if session.status in {SessionStatus.COMPLETED, SessionStatus.ABANDONED}:
            return session
        session.status = SessionStatus.ABANDONED
        session.save(update_fields=["status", "modified"])
        return session

    @classmethod
    @transaction.atomic
    def complete(cls, session: CheckoutSession) -> Order:
        """
        Finalise checkout: create Order and mark session COMPLETED.
        Raises CheckoutIncompleteError if required fields are missing.
        """
        if not session.shipping_address_id or not session.shipping_method:
            msg = "Checkout session is missing shipping address or shipping method."
            raise CheckoutIncompleteError(msg)
        result = cls.place_order(session)
        return result.order

    # Place order (the full pipeline)

    @classmethod
    @transaction.atomic
    def place_order(cls, session: CheckoutSession) -> PlaceOrderResult:
        """Run the full order placement pipeline."""
        cls._assert_mutable(session)
        cls._assert_not_expired(session)

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

        shipping_address = session.shipping_address
        billing_address = session.billing_address
        if shipping_address is None or billing_address is None:
            raise ValidationError(
                _("Shipping and billing addresses must be set before placing an order.")
            )

        shipping_snap = CustomerService.snapshot_address(shipping_address)
        billing_snap = CustomerService.snapshot_address(billing_address)

        shipping_method_id: UUID | None = None
        if session.shipping_method:
            try:
                shipping_method_id = (
                    ShippingMethod.objects.only("pk")
                    .get(name=session.shipping_method)
                    .pk
                )
            except ShippingMethod.DoesNotExist as exc:
                raise CheckoutError(
                    str(_("Selected shipping method is no longer available."))
                ) from exc

        currency = session.currency or PricingService.get_default_currency()

        lines = cls._resolve_order_lines(
            cart_items,
            currency,
            country=shipping_snap.get("country", ""),
            state=shipping_snap.get("state", ""),
        )

        coupon = None
        discount_amount = Decimal("0.00")

        if session.coupon_code and session.customer:
            cart_sub_total = sum(
                (line.unit_price * line.quantity for line in lines),
                Decimal("0.00"),
            )
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
                shipping_method=shipping_method_id,
                shipping_method_name=session.shipping_method,
            )
        )

        if coupon is not None and session.customer:
            CouponService.redeem(
                coupon,
                customer=session.customer,
                order=order,
            )

        session.status = SessionStatus.COMPLETED
        session.order = order
        session.save(update_fields=["status", "order", "modified"])

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

            try:
                resolved_price = PricingService.get_current_price(variant, currency)
            except NoPriceFoundError as err:
                raise NoPriceFoundError(
                    sku=variant.sku, currency_code=currency.code
                ) from err

            product = variant.product
            warehouse = None
            if product.is_shippable:
                warehouse = StockMovementService.select_warehouse(variant, ci.quantity)
                if warehouse is None:
                    raise InsufficientStockError(
                        sku=variant.sku,
                        requested=ci.quantity,
                        available=StockMovementService.get_available_quantity(variant),
                    )

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
