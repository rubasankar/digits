from __future__ import annotations

import pytest
from django.test import SimpleTestCase

from core.exceptions import CheckoutAlreadyCompletedError
from core.exceptions import CheckoutError
from core.exceptions import CheckoutSessionExpiredError
from core.exceptions import CouponAlreadyUsedByCustomerError
from core.exceptions import CouponError
from core.exceptions import CouponExpiredError
from core.exceptions import CouponInactiveError
from core.exceptions import CouponNotFoundError
from core.exceptions import CouponUsageLimitReachedError
from core.exceptions import DomainError
from core.exceptions import EmptyCartError
from core.exceptions import InsufficientStockError
from core.exceptions import InvalidStatusTransitionError
from core.exceptions import NoPriceFoundError
from core.exceptions import NotFoundError
from core.exceptions import OrderNotEligibleForReturnError
from core.exceptions import PaymentAlreadyRefundedError
from core.exceptions import PaymentError
from core.exceptions import PermissionDeniedError
from core.exceptions import PricingError
from core.exceptions import RefundExceedsPaymentError
from core.exceptions import ReturnAlreadyExistsError
from core.exceptions import ReturnError
from core.exceptions import ReturnQuantityExceededError

# ---------------------------------------------------------------------------
# DomainError base
# ---------------------------------------------------------------------------


class DomainErrorTests(SimpleTestCase):
    def test_default_message(self) -> None:
        err = DomainError()
        assert str(err) == "A business rule was violated."
        assert err.message == "A business rule was violated."

    def test_custom_message(self) -> None:
        err = DomainError("Something went wrong.")
        assert str(err) == "Something went wrong."

    def test_is_exception_subclass(self) -> None:
        assert issubclass(DomainError, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(DomainError):
            msg = "test"
            raise DomainError(msg)


# ---------------------------------------------------------------------------
# Generic errors
# ---------------------------------------------------------------------------


class NotFoundErrorTests(SimpleTestCase):
    def test_default_message_mentions_not_found(self) -> None:
        assert "not found" in str(NotFoundError()).lower()

    def test_custom_message(self) -> None:
        err = NotFoundError("Order not found.")
        assert str(err) == "Order not found."

    def test_is_domain_error(self) -> None:
        assert isinstance(NotFoundError(), DomainError)


class PermissionDeniedErrorTests(SimpleTestCase):
    def test_default_message_mentions_permission(self) -> None:
        assert "permission" in str(PermissionDeniedError()).lower()

    def test_custom_message(self) -> None:
        err = PermissionDeniedError("Nope.")
        assert str(err) == "Nope."

    def test_is_domain_error(self) -> None:
        assert isinstance(PermissionDeniedError(), DomainError)


# ---------------------------------------------------------------------------
# Status machine
# ---------------------------------------------------------------------------


class InvalidStatusTransitionErrorTests(SimpleTestCase):
    def _make(self, **kwargs: str) -> InvalidStatusTransitionError:
        return InvalidStatusTransitionError(
            entity=kwargs.get("entity", "Order"),
            from_status=kwargs.get("from_status", "PENDING"),
            to_status=kwargs.get("to_status", "SHIPPED"),
        )

    def test_attributes_stored(self) -> None:
        err = self._make()
        assert err.entity == "Order"
        assert err.from_status == "PENDING"
        assert err.to_status == "SHIPPED"

    def test_default_message_contains_all_three_parts(self) -> None:
        err = self._make()
        msg = str(err)
        assert "Order" in msg
        assert "PENDING" in msg
        assert "SHIPPED" in msg

    def test_custom_message_overrides_default(self) -> None:
        err = InvalidStatusTransitionError(
            entity="Order",
            from_status="PENDING",
            to_status="SHIPPED",
            message="Custom.",
        )
        assert str(err) == "Custom."

    def test_is_domain_error(self) -> None:
        assert isinstance(self._make(), DomainError)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


class InsufficientStockErrorTests(SimpleTestCase):
    def test_attributes_stored(self) -> None:
        err = InsufficientStockError(sku="SKU-1", requested=10, available=3)
        assert err.sku == "SKU-1"
        assert err.requested == 10
        assert err.available == 3

    def test_default_message_contains_sku_and_quantities(self) -> None:
        err = InsufficientStockError(sku="SKU-1", requested=10, available=3)
        msg = str(err)
        assert "SKU-1" in msg
        assert "10" in msg
        assert "3" in msg

    def test_custom_message(self) -> None:
        err = InsufficientStockError(
            sku="SKU-1", requested=10, available=3, message="Out of stock."
        )
        assert str(err) == "Out of stock."

    def test_is_domain_error(self) -> None:
        assert isinstance(
            InsufficientStockError(sku="X", requested=1, available=0), DomainError
        )


# ---------------------------------------------------------------------------
# Coupons / Promotions
# ---------------------------------------------------------------------------


class CouponErrorHierarchyTests(SimpleTestCase):
    def test_all_subclass_coupon_error(self) -> None:
        for cls in (
            CouponNotFoundError,
            CouponExpiredError,
            CouponInactiveError,
            CouponUsageLimitReachedError,
            CouponAlreadyUsedByCustomerError,
        ):
            assert issubclass(cls, CouponError), f"{cls} is not a CouponError"

    def test_coupon_error_is_domain_error(self) -> None:
        assert issubclass(CouponError, DomainError)


class CouponErrorMessageTests(SimpleTestCase):
    def test_base_default_message(self) -> None:
        assert "coupon" in str(CouponError()).lower()

    def test_not_found_default_message(self) -> None:
        assert "found" in str(CouponNotFoundError()).lower()

    def test_expired_default_message(self) -> None:
        assert "expired" in str(CouponExpiredError()).lower()

    def test_inactive_default_message(self) -> None:
        assert "active" in str(CouponInactiveError()).lower()

    def test_usage_limit_default_message(self) -> None:
        assert "limit" in str(CouponUsageLimitReachedError()).lower()

    def test_already_used_default_message(self) -> None:
        assert "already used" in str(CouponAlreadyUsedByCustomerError()).lower()


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


class NoPriceFoundErrorTests(SimpleTestCase):
    def test_attributes_stored(self) -> None:
        err = NoPriceFoundError(sku="VAR-1", currency_code="USD")
        assert err.sku == "VAR-1"
        assert err.currency_code == "USD"

    def test_default_message_contains_sku_and_currency(self) -> None:
        err = NoPriceFoundError(sku="VAR-1", currency_code="USD")
        assert "VAR-1" in str(err)
        assert "USD" in str(err)

    def test_custom_message(self) -> None:
        err = NoPriceFoundError(sku="X", currency_code="Y", message="No price.")
        assert str(err) == "No price."

    def test_is_pricing_error(self) -> None:
        assert isinstance(NoPriceFoundError(sku="X", currency_code="Y"), PricingError)

    def test_is_domain_error(self) -> None:
        assert isinstance(NoPriceFoundError(sku="X", currency_code="Y"), DomainError)


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------


class CheckoutErrorHierarchyTests(SimpleTestCase):
    def test_all_subclass_checkout_error(self) -> None:
        for cls in (
            EmptyCartError,
            CheckoutSessionExpiredError,
            CheckoutAlreadyCompletedError,
        ):
            assert issubclass(cls, CheckoutError), f"{cls} is not a CheckoutError"

    def test_checkout_error_is_domain_error(self) -> None:
        assert issubclass(CheckoutError, DomainError)


class CheckoutErrorMessageTests(SimpleTestCase):
    def test_base_default_message(self) -> None:
        assert "checkout" in str(CheckoutError()).lower()

    def test_empty_cart_default_message(self) -> None:
        assert "empty" in str(EmptyCartError()).lower()

    def test_session_expired_default_message(self) -> None:
        assert "expired" in str(CheckoutSessionExpiredError()).lower()

    def test_already_completed_default_message(self) -> None:
        assert "completed" in str(CheckoutAlreadyCompletedError()).lower()


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


class PaymentErrorHierarchyTests(SimpleTestCase):
    def test_all_subclass_payment_error(self) -> None:
        for cls in (RefundExceedsPaymentError, PaymentAlreadyRefundedError):
            assert issubclass(cls, PaymentError), f"{cls} is not a PaymentError"

    def test_payment_error_is_domain_error(self) -> None:
        assert issubclass(PaymentError, DomainError)


class RefundExceedsPaymentErrorTests(SimpleTestCase):
    def test_attributes_stored(self) -> None:
        err = RefundExceedsPaymentError(refund_amount=200, payment_amount=100)
        assert err.refund_amount == 200
        assert err.payment_amount == 100

    def test_default_message_contains_amounts(self) -> None:
        err = RefundExceedsPaymentError(refund_amount=200, payment_amount=100)
        assert "200" in str(err)
        assert "100" in str(err)

    def test_custom_message(self) -> None:
        err = RefundExceedsPaymentError(
            refund_amount=200, payment_amount=100, message="Too much."
        )
        assert str(err) == "Too much."


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------


class ReturnErrorHierarchyTests(SimpleTestCase):
    def test_all_subclass_return_error(self) -> None:
        for cls in (
            OrderNotEligibleForReturnError,
            ReturnAlreadyExistsError,
            ReturnQuantityExceededError,
        ):
            assert issubclass(cls, ReturnError), f"{cls} is not a ReturnError"

    def test_return_error_is_domain_error(self) -> None:
        assert issubclass(ReturnError, DomainError)


class ReturnQuantityExceededErrorTests(SimpleTestCase):
    def test_attributes_stored(self) -> None:
        err = ReturnQuantityExceededError(sku="SKU-A", requested=5, max_returnable=2)
        assert err.sku == "SKU-A"
        assert err.requested == 5
        assert err.max_returnable == 2

    def test_default_message_contains_sku_and_quantities(self) -> None:
        err = ReturnQuantityExceededError(sku="SKU-A", requested=5, max_returnable=2)
        msg = str(err)
        assert "SKU-A" in msg
        assert "5" in msg
        assert "2" in msg

    def test_custom_message(self) -> None:
        err = ReturnQuantityExceededError(
            sku="SKU-A", requested=5, max_returnable=2, message="Custom."
        )
        assert str(err) == "Custom."
