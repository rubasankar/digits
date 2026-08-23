from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from .enums import CheckoutStep
from .enums import SessionStatus


class CheckoutSession(UUIDModel, TimeStampedModel):
    cart = models.OneToOneField(
        "shopping.Cart",
        verbose_name=_("Cart"),
        on_delete=models.PROTECT,
        related_name="checkout_session",
        help_text=_("The cart this checkout is processing."),
    )
    order = models.OneToOneField(
        "orders.Order",
        verbose_name=_("Order"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout_session",
        help_text=_("Set after the payment is confirmed and the Order is created."),
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout_sessions",
        help_text=_("Null for guest checkouts. Identified by cart.session_key."),
    )

    shipping_address = models.ForeignKey(
        "customers.CustomerAddress",
        verbose_name=_("Shipping Address"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipping_checkout_sessions",
        help_text=_(
            "Selected shipping address. At order creation this is snapshotted "
            "into Order.shipping_address (JSON) so later edits don't affect the order."
        ),
    )
    billing_address = models.ForeignKey(
        "customers.CustomerAddress",
        verbose_name=_("Billing Address"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_checkout_sessions",
        help_text=_(
            "Selected billing address. Snapshotted into Order.billing_address (JSON) "
            "at order creation."
        ),
    )

    shipping_method = models.CharField(
        _("Shipping Method"),
        max_length=100,
        blank=True,
        help_text=_("Name of the shipping method selected, e.g. 'Standard Post'."),
    )
    shipping_cost = models.DecimalField(
        _("Shipping Cost"),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_("Quoted cost for the selected shipping method."),
    )

    currency = models.ForeignKey(
        "pricing.Currency",
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="checkout_sessions",
    )
    coupon_code = models.CharField(
        _("Coupon Code"),
        max_length=50,
        blank=True,
        help_text=_("Code applied by the customer. Validated in the checkout service."),
    )

    status = models.CharField(
        _("Status"),
        max_length=12,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
        db_index=True,
    )
    step = models.CharField(
        _("Current Step"),
        max_length=12,
        choices=CheckoutStep.choices,
        default=CheckoutStep.ADDRESS,
    )
    expires_at = models.DateTimeField(
        _("Expires At"),
        null=True,
        blank=True,
        help_text=_(
            "When this session should be considered stale. "
            "Set to e.g. now + 24 hours when the session is created."
        ),
    )

    class Meta:
        verbose_name = _("Checkout Session")
        verbose_name_plural = _("Checkout Sessions")
        ordering = ["-created"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(shipping_cost__gte=0),
                name="checkout_session_shipping_cost_non_negative",
            ),
            # COMPLETED status requires order to be set
            models.CheckConstraint(
                condition=~Q(status="COMPLETED") | Q(order__isnull=False),
                name="checkout_completed_requires_order",
            ),
            # ADDRESS step requires shipping_address to be set
            models.CheckConstraint(
                condition=~Q(step="ADDRESS") | Q(shipping_address__isnull=False),
                name="checkout_address_step_requires_address",
            ),
            # PAYMENT step requires billing_address to be set
            models.CheckConstraint(
                condition=~Q(step="PAYMENT") | Q(billing_address__isnull=False),
                name="checkout_payment_step_requires_billing",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        self._validate_step_requirements()
        self._validate_status_requirements()

    def _validate_step_requirements(self) -> None:
        if self.step == CheckoutStep.ADDRESS and not self.shipping_address_id:
            raise ValidationError(
                {"shipping_address": _("Shipping address is required at ADDRESS step.")}
            )

        if self.step == CheckoutStep.PAYMENT and not self.billing_address_id:
            raise ValidationError(
                {"billing_address": _("Billing address is required at PAYMENT step.")}
            )

    def _validate_status_requirements(self) -> None:
        if self.status == SessionStatus.COMPLETED and not self.order_id:
            raise ValidationError(
                {"order": _("Order must be set when status is COMPLETED.")}
            )

    def __str__(self) -> str:
        owner = str(self.customer) if self.customer else "guest"
        return f"Checkout({self.status}) -- {owner} cart={self.cart}"

    def __repr__(self) -> str:
        return (
            f"<CheckoutSession id={self.id} status={self.status} "
            f"customer={self.customer} cart={self.cart} order={self.order}>"
        )
