class DomainError(Exception):
    """
    Base class for all business-rule violations raised by service methods.

    Always carries a human-readable ``message`` suitable for display in
    API error responses.  Never expose raw Python tracebacks to end-users.
    """

    default_message: str = "A business rule was violated."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


# Generic


class NotFoundError(DomainError):
    """A requested resource does not exist."""

    default_message = "The requested resource was not found."


class PermissionDeniedError(DomainError):
    """The caller is not allowed to perform this action."""

    default_message = "You do not have permission to perform this action."


# Status machine


class InvalidStatusTransitionError(DomainError):
    """
    A state-machine transition was attempted that is not allowed.

    Example: trying to SHIP an order that is still PENDING.
    """

    def __init__(
        self,
        *,
        entity: str,
        from_status: str,
        to_status: str,
        message: str | None = None,
    ) -> None:
        self.entity = entity
        self.from_status = from_status
        self.to_status = to_status
        default = f"Cannot transition {entity} from '{from_status}' to '{to_status}'."
        super().__init__(message or default)


# Inventory


class InsufficientStockError(DomainError):
    """
    A stock reservation or allocation failed because available quantity
    is lower than the requested amount.
    """

    def __init__(
        self,
        *,
        sku: str,
        requested: int,
        available: int,
        message: str | None = None,
    ) -> None:
        self.sku = sku
        self.requested = requested
        self.available = available
        default = (
            f"Insufficient stock for '{sku}': "
            f"requested {requested}, available {available}."
        )
        super().__init__(message or default)


# Coupons / Promotions


class CouponError(DomainError):
    """Base class for all coupon-related failures."""

    default_message = "The coupon could not be applied."


class CouponNotFoundError(CouponError):
    default_message = "No coupon with that code was found."


class CouponExpiredError(CouponError):
    default_message = "This coupon has expired."


class CouponInactiveError(CouponError):
    default_message = "This coupon is not currently active."


class CouponUsageLimitReachedError(CouponError):
    default_message = "This coupon has reached its maximum usage limit."


class CouponAlreadyUsedByCustomerError(CouponError):
    default_message = "You have already used this coupon the maximum number of times."


# Pricing


class PricingError(DomainError):
    """Base class for pricing failures."""

    default_message = "A pricing error occurred."


class NoPriceFoundError(PricingError):
    """No active price exists for the requested variant / currency combination."""

    def __init__(
        self, *, sku: str, currency_code: str, message: str | None = None
    ) -> None:
        self.sku = sku
        self.currency_code = currency_code
        default = f"No price found for variant '{sku}' in currency '{currency_code}'."
        super().__init__(message or default)


# Checkout


class CheckoutError(DomainError):
    """Base class for checkout failures."""

    default_message = "A checkout error occurred."


class EmptyCartError(CheckoutError):
    default_message = "Cannot start checkout with an empty cart."


class CheckoutSessionExpiredError(CheckoutError):
    default_message = "This checkout session has expired. Please start again."


class CheckoutAlreadyCompletedError(CheckoutError):
    default_message = "This checkout session has already been completed."


# Payments


class PaymentError(DomainError):
    """Base class for payment failures."""

    default_message = "A payment error occurred."


class RefundExceedsPaymentError(PaymentError):
    """The requested refund amount exceeds the original payment amount."""

    def __init__(
        self,
        *,
        refund_amount: object,
        payment_amount: object,
        message: str | None = None,
    ) -> None:
        self.refund_amount = refund_amount
        self.payment_amount = payment_amount
        default = (
            f"Refund amount ({refund_amount}) exceeds "
            f"original payment amount ({payment_amount})."
        )
        super().__init__(message or default)


class PaymentAlreadyRefundedError(PaymentError):
    default_message = "This payment has already been fully refunded."


# Returns


class ReturnError(DomainError):
    """Base class for return-request failures."""

    default_message = "A return request error occurred."


class OrderNotEligibleForReturnError(ReturnError):
    """The order is not in a state that allows a return to be requested."""

    default_message = "This order is not eligible for a return request."


class ReturnAlreadyExistsError(ReturnError):
    """A non-terminal return request already exists for this order."""

    default_message = "An active return request already exists for this order."


class ReturnQuantityExceededError(ReturnError):
    """The quantity requested for return exceeds what can still be returned."""

    def __init__(
        self,
        *,
        sku: str,
        requested: int,
        max_returnable: int,
        message: str | None = None,
    ) -> None:
        self.sku = sku
        self.requested = requested
        self.max_returnable = max_returnable
        default = (
            f"Cannot return {requested} unit(s) of '{sku}': "
            f"only {max_returnable} unit(s) are eligible for return."
        )
        super().__init__(message or default)
