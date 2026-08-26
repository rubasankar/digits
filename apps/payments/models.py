from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from .enums import PaymentStatusEnum
from .enums import RefundStatusEnum

User = get_user_model()


class PaymentMethod(UUIDModel, TimeStampedModel):
    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
        help_text=_("Display name shown to customers, e.g. 'Credit / Debit Card'."),
    )
    gateway_code = models.CharField(
        _("Gateway Code"),
        max_length=50,
        blank=True,
        help_text=_(
            "Machine code passed to the payment gateway adapter, "
            "e.g. 'card', 'upi'. Leave blank for offline methods."
        ),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Optional detail shown to the customer at checkout."),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Inactive methods are hidden from checkout but historical "
            "payment records keep their method."
        ),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Controls order in the checkout payment step. Lower = first."),
    )

    class Meta:
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return (
            f"<PaymentMethod id={self.id} name={self.name!r} active={self.is_active}>"
        )


class RefundReason(UUIDModel, TimeStampedModel):
    name = models.CharField(
        _("Reason"),
        max_length=150,
        unique=True,
        help_text=_("e.g. 'Item Damaged / Defective', 'Customer Changed Mind'."),
    )
    description = models.TextField(
        _("Description"),
        blank=True,
        help_text=_("Optional internal notes about when to use this reason."),
    )
    requires_return = models.BooleanField(
        _("Requires Item Return"),
        default=False,
        help_text=_(
            "If True, the refund workflow will prompt staff to confirm "
            "the item has been returned before issuing the refund."
        ),
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text=_(
            "Inactive reasons are hidden from new refund forms "
            "but existing refunds keep their reason."
        ),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Controls order in the refund form. Lower = first."),
    )

    class Meta:
        verbose_name = _("Refund Reason")
        verbose_name_plural = _("Refund Reasons")
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<RefundReason id={self.id} name={self.name!r}>"


class Payment(UUIDModel, TimeStampedModel):
    PaymentStatus = PaymentStatusEnum

    # Terminal statuses -- payment service sets completed_at when reached.
    # PARTIALLY_REFUNDED is deliberately excluded: it's the only status with
    # an outgoing transition (-> REFUNDED, see _PAYMENT_TRANSITIONS), so it
    # isn't actually terminal. In practice this doesn't change completed_at's
    # value either way -- the only path to PARTIALLY_REFUNDED is via PAID,
    # which already stamped it -- but keeping it out matches the field's
    # real semantics.
    TERMINAL_STATUSES = {
        PaymentStatus.PAID,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
        PaymentStatus.REFUNDED,
    }

    order = models.ForeignKey(
        "orders.Order",
        verbose_name=_("Order"),
        on_delete=models.PROTECT,
        related_name="payments",
    )
    gateway = models.CharField(
        _("Payment Gateway"),
        max_length=50,
        help_text=_("Provider identifier, e.g. 'stripe', 'paypal', 'razorpay'."),
    )
    transaction_id = models.CharField(
        _("Transaction ID"),
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Provider's unique transaction reference."),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        help_text=_(
            "Do not edit directly. "
            "Use the payment service which also writes a PaymentStatusHistory row."
        ),
    )
    amount = models.DecimalField(
        _("Amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Total amount charged, inclusive of tax."),
    )
    currency = models.ForeignKey(
        "pricing.Currency",
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        verbose_name=_("Payment Method"),
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
        help_text=_(
            "How the customer paid. "
            "Manage available methods in Payment - Payment Methods."
        ),
    )
    raw_response = models.JSONField(
        _("Raw Gateway Response"),
        default=dict,
        help_text=_("Full JSON payload from the gateway. Never expose to customers."),
    )
    initiated_at = models.DateTimeField(
        _("Initiated At"),
        auto_now_add=True,
    )
    completed_at = models.DateTimeField(
        _("Completed At"),
        null=True,
        blank=True,
        help_text=_("Set by the payment service when a terminal status is reached."),
    )

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-initiated_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payment_amount_non_negative",
            ),
        ]

    def __str__(self) -> str:
        try:
            status_label = self.PaymentStatus(self.status).label
        except ValueError:
            status_label = self.status
        return f"{self.gateway} | {self.transaction_id} | {status_label}"

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} order={self.order} "
            f"gateway={self.gateway!r} status={self.status} amount={self.amount}>"
        )


class PaymentStatusHistory(models.Model):
    payment = models.ForeignKey(
        Payment,
        verbose_name=_("Payment"),
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(
        _("Previous Status"),
        max_length=20,
        choices=Payment.PaymentStatus.choices,
        blank=True,
        help_text=_("Empty for the initial status entry."),
    )
    new_status = models.CharField(
        _("New Status"),
        max_length=20,
        choices=Payment.PaymentStatus.choices,
    )
    changed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Changed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_status_changes",
        help_text=_("Null when triggered by an automated gateway callback."),
    )
    gateway_event = models.CharField(
        _("Gateway Event"),
        max_length=100,
        blank=True,
        help_text=_(
            "The gateway webhook event that triggered this transition, "
            "e.g. 'payment_intent.succeeded', 'charge.failed'."
        ),
    )
    note = models.TextField(_("Note"), blank=True)
    changed_at = models.DateTimeField(_("Changed At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Payment Status History")
        verbose_name_plural = _("Payment Status Histories")
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return (
            f"Payment {self.payment}: {self.old_status or '(new)'} - {self.new_status}"
        )

    def __repr__(self) -> str:
        return (
            f"<PaymentStatusHistory id={self.id} payment={self.payment} "
            f"{self.old_status!r}-{self.new_status!r}>"
        )


class RefundItem(UUIDModel, TimeStampedModel):
    refund = models.ForeignKey(
        "payments.Refund",
        verbose_name=_("Refund"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        verbose_name=_("Order Item"),
        on_delete=models.PROTECT,
        related_name="refund_items",
    )
    quantity = models.PositiveSmallIntegerField(
        _("Quantity"),
        help_text=_("Number of units refunded in this line item."),
    )
    amount = models.DecimalField(
        _("Amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Refund amount for this line item."),
    )

    class Meta:
        verbose_name = _("Refund Item")
        verbose_name_plural = _("Refund Items")
        ordering = ["refund", "order_item"]
        constraints = [
            models.UniqueConstraint(
                fields=["refund", "order_item"],
                name="unique_refund_item_per_refund_order_item",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="refund_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="refund_item_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order_item.variant_sku} x {self.quantity} = {self.amount}"

    def __repr__(self) -> str:
        return (
            f"<RefundItem id={self.id} refund={self.refund} "
            f"order_item={self.order_item} qty={self.quantity} amount={self.amount}>"
        )


class Refund(UUIDModel, TimeStampedModel):
    RefundStatus = RefundStatusEnum

    payment = models.ForeignKey(
        Payment,
        verbose_name=_("Payment"),
        on_delete=models.PROTECT,
        related_name="refunds",
    )
    transaction_id = models.CharField(
        _("Refund Transaction ID"),
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Provider's refund reference, if issued."),
    )
    amount = models.DecimalField(
        _("Refund Amount"),
        max_digits=12,
        decimal_places=2,
    )
    reason = models.ForeignKey(
        RefundReason,
        verbose_name=_("Reason"),
        on_delete=models.PROTECT,
        related_name="refunds",
        null=True,
        blank=True,
        help_text=_(
            "Why this refund was issued. Manage reasons in Payment - Refund Reasons."
        ),
    )
    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text=_("Additional detail about why this refund was issued."),
    )
    status = models.CharField(
        _("Status"),
        max_length=12,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
        db_index=True,
    )
    refunded_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Refunded By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_refunds",
        help_text=_("Staff user who triggered the refund. Null if automated."),
    )

    class Meta:
        verbose_name = _("Refund")
        verbose_name_plural = _("Refunds")
        ordering = ["-created"]
        constraints = [
            # Refund amount must be positive -- zero-value refunds are nonsensical.
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="refund_amount_positive",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.amount is not None and self.amount <= 0:
            raise ValidationError(
                {"amount": _("Refund amount must be greater than zero.")}
            )

        if self.amount is not None and self.payment_id:
            payment = self.payment

            # Per-refund ceiling: can never exceed the full payment in one go.
            if self.amount > payment.amount:
                raise ValidationError(
                    {
                        "amount": _(
                            "Refund amount (%(refund)s) cannot exceed the payment "
                            "amount (%(payment)s)."
                        )
                        % {"refund": self.amount, "payment": payment.amount}
                    }
                )

            # Cumulative ceiling: all refunds against this payment combined must
            # not exceed the original payment amount.
            # Exclude FAILED refunds from the cumulative check.
            existing_qs = payment.refunds.exclude(status=RefundStatusEnum.FAILED)
            if self.pk:
                # Exclude the current refund when editing an existing record.
                existing_qs = existing_qs.exclude(pk=self.pk)

            already_refunded = existing_qs.aggregate(total=Sum("amount"))["total"] or 0
            if already_refunded + self.amount > payment.amount:
                raise ValidationError(
                    {
                        "amount": _(
                            "This refund (%(refund)s) would bring the total refunded "
                            "(%(total)s) above the original payment amount "
                            "(%(payment)s)."
                        )
                        % {
                            "refund": self.amount,
                            "total": already_refunded + self.amount,
                            "payment": payment.amount,
                        }
                    }
                )

    def __str__(self) -> str:
        status_label = dict(self.RefundStatus.choices).get(self.status, self.status)
        return (
            f"Refund {self.id} -- "
            f"{self.payment.currency.symbol}{self.amount} "
            f"({status_label})"
        )

    def __repr__(self) -> str:
        return (
            f"<Refund id={self.id} payment={self.payment} "
            f"amount={self.amount} status={self.status}>"
        )
