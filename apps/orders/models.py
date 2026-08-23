from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.payments.enums import PaymentStatusEnum

from .enums import OrderStatusEnum
from .enums import ReturnReasonEnum
from .enums import ReturnRequestStatusEnum


class Order(UUIDModel, TimeStampedModel):
    number = models.CharField(
        _("Order Number"),
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_(
            "Human-readable reference generated at placement, e.g. ORD-00001234."
        ),
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Customer"),
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        _("Order Status"),
        max_length=20,
        choices=OrderStatusEnum.choices,
        default=OrderStatusEnum.PENDING,
        db_index=True,
    )

    # Address snapshots -- immutable JSON copies taken at checkout.
    shipping_address = models.JSONField(
        _("Shipping Address"),
        help_text=_(
            "Snapshot of the delivery address at checkout time. "
            "Keys: full_name, contact_number, address_line1, address_line2, "
            "landmark, city, state, country, pincode."
        ),
    )
    billing_address = models.JSONField(
        _("Billing Address"),
        help_text=_(
            "Snapshot of the billing address. Same structure as shipping_address."
        ),
    )

    # Currency & financials
    currency = models.ForeignKey(
        "pricing.Currency",
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        related_name="orders",
    )
    sub_total = models.DecimalField(
        _("Sub-total"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Sum of line totals before discounts, shipping, and tax."),
    )
    discount_amount = models.DecimalField(
        _("Discount Amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    shipping_cost = models.DecimalField(
        _("Shipping Cost"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    tax_amount = models.DecimalField(
        _("Tax Amount"),
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    total_amount = models.DecimalField(
        _("Total Amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("sub_total - discount_amount + shipping_cost + tax_amount."),
    )

    # Promotion
    coupon_code = models.CharField(
        _("Coupon Code Used"),
        max_length=50,
        blank=True,
        help_text=_(
            "Denormalised for display. Full audit in promotion.CouponRedemption."
        ),
    )

    # Payment
    payment_status = models.CharField(
        _("Payment Status"),
        max_length=20,
        choices=PaymentStatusEnum.choices,
        default=PaymentStatusEnum.UNPAID,
        db_index=True,
    )
    notes = models.TextField(_("Customer / Staff Notes"), blank=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ["-created"]
        constraints = [
            # All financial snapshot fields must be non-negative.
            models.CheckConstraint(
                condition=models.Q(sub_total__gte=0),
                name="order_sub_total_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="order_discount_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(shipping_cost__gte=0),
                name="order_shipping_cost_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="order_tax_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="order_total_amount_non_negative",
            ),
            # Total amount must match formula
            models.CheckConstraint(
                condition=models.Q(
                    total_amount=models.F("sub_total")
                    - models.F("discount_amount")
                    + models.F("shipping_cost")
                    + models.F("tax_amount")
                ),
                name="order_total_amount_formula",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    def __repr__(self) -> str:
        return (
            f"<Order id={self.id} number={self.number!r} "
            f"customer={self.customer} "
            f"status={self.status} payment={self.payment_status}>"
        )


class OrderItem(UUIDModel, TimeStampedModel):
    order = models.ForeignKey(
        Order,
        verbose_name=_("Order"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        "catalogue.ProductVariant",
        verbose_name=_("Product Variant"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
        help_text=_("Live reference for reporting. Null if variant is deleted."),
    )

    #  Catalogue snapshots (written once, never updated)
    variant_sku = models.CharField(_("SKU (snapshot)"), max_length=100)
    variant_name = models.CharField(_("Product Name (snapshot)"), max_length=255)
    variant_attributes = models.JSONField(
        _("Variant Attributes (snapshot)"),
        default=dict,
        help_text=_(
            "Dict of label-value pairs at order time, "
            "e.g. {'Colour': 'Red', 'Size': 'M'}."
        ),
    )

    #  Pricing snapshots
    unit_price = models.DecimalField(
        _("Unit Price"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Pre-tax price per unit at purchase time."),
    )
    tax_rate = models.DecimalField(
        _("Tax Rate (%)"),
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text=_("Tax percentage applied at purchase time."),
    )
    quantity = models.PositiveSmallIntegerField(_("Quantity"))
    line_total = models.DecimalField(
        _("Line Total"),
        max_digits=12,
        decimal_places=2,
        help_text=_("unit_price x quantity (pre-tax)."),
    )

    class Meta:
        verbose_name = _("Order Item")
        verbose_name_plural = _("Order Items")
        ordering = ["order", "variant_sku"]
        constraints = [
            # Quantity must be at least 1 -- a zero-unit line item is nonsensical.
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_item_quantity_gte_1",
            ),
            # unit_price and line_total must be non-negative snapshots.
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_item_unit_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name="order_item_line_total_non_negative",
            ),
            # tax_rate must be non-negative
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0),
                name="order_item_tax_rate_non_negative",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.unit_price is not None and self.quantity:
            expected_line_total = self.unit_price * self.quantity
            if self.line_total != expected_line_total:
                raise ValidationError(
                    {
                        "line_total": _(
                            "Line total (%s) must equal "
                            "unit_price (%s) x quantity (%s) = %s."
                        )
                        % (
                            self.line_total,
                            self.unit_price,
                            self.quantity,
                            expected_line_total,
                        )
                    }
                )

    def __str__(self) -> str:
        return f"{self.variant_name} x {self.quantity} (order {self.order})"

    def __repr__(self) -> str:
        return (
            f"<OrderItem id={self.id} order={self.order} "
            f"sku={self.variant_sku!r} qty={self.quantity}>"
        )


class StatusHistoryBase(models.Model):
    # Subclasses must override these with the appropriate choices.
    old_status = models.CharField(
        _("Previous Status"),
        max_length=30,
        blank=True,
        help_text=_("Empty for the initial status entry."),
    )
    new_status = models.CharField(
        _("New Status"),
        max_length=30,
    )
    changed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Changed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Null when triggered by an automated process."),
        related_name="%(app_label)s_%(class)s_status_changes",
    )
    note = models.TextField(_("Note"), blank=True)
    changed_at = models.DateTimeField(_("Changed At"), auto_now_add=True)

    class Meta:
        abstract = True


class OrderStatusHistory(StatusHistoryBase):
    order = models.ForeignKey(
        Order,
        verbose_name=_("Order"),
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    # Narrow the inherited char fields to the order status choices.
    old_status = models.CharField(
        _("Previous Status"),
        max_length=20,
        choices=OrderStatusEnum.choices,
        blank=True,
        help_text=_("Empty for the very first status entry."),
    )
    new_status = models.CharField(
        _("New Status"),
        max_length=20,
        choices=OrderStatusEnum.choices,
    )
    changed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Changed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
        help_text=_("Null when the transition is triggered by an automated process."),
    )

    class Meta:
        verbose_name = _("Order Status History")
        verbose_name_plural = _("Order Status Histories")
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return (
            f"Order {self.order.number}: "
            f"{self.old_status or '(new)'} - {self.new_status}"
        )

    def __repr__(self) -> str:
        return (
            f"<OrderStatusHistory id={self.id} order={self.order_id} "
            f"{self.old_status!r}-{self.new_status!r}>"
        )


# Return Request models

#
# Lifecycle overview
#
#   Customer           Staff / Warehouse           Payment
#   Submits request    Reviews request
#   (PENDING)          Approves / Rejects
#                      --> APPROVED / REJECTED
#   Ships items back
#   --> RETURN_SHIPPED
#                      Confirms receipt
#   --> RECEIVED
#                                                  Initiates refund via
#                                                  payments.Refund
#                      Marks completed
#   --> COMPLETED
#
# Service responsibilities (ReturnRequestService)
#
#  - create()       : validate order status is DELIVERED, create
#                     ReturnRequest + ReturnRequestItems in one transaction,
#                     transition Order.status -> RETURN_REQUESTED.
#  - approve()      : PENDING -> APPROVED, write status history row.
#  - reject()       : PENDING -> REJECTED, write status history row,
#                     restore Order.status -> DELIVERED.
#  - mark_shipped() : APPROVED -> RETURN_SHIPPED, store tracking number on
#                     ReturnShipment.
#  - receive()      : RETURN_SHIPPED -> RECEIVED, record received quantities
#                     on ReturnRequestItem.quantity_received, restock via
#                     inventory.StockMovementService (RETURN movement).
#  - complete()     : RECEIVED -> COMPLETED, transition Order.status -> RETURNED,
#                     trigger payments.Refund creation if not already done.
#  - cancel()       : PENDING -> CANCELLED (customer only), restore Order.status.
#


class ReturnRequest(UUIDModel, TimeStampedModel):
    ReturnStatus = ReturnRequestStatusEnum
    ReturnReason = ReturnReasonEnum

    # Terminal statuses - no further transitions allowed.
    TERMINAL_STATUSES: frozenset[str] = frozenset(
        {
            ReturnStatus.COMPLETED,
            ReturnStatus.REJECTED,
            ReturnStatus.CANCELLED,
        }
    )

    order = models.ForeignKey(
        Order,
        verbose_name=_("Order"),
        on_delete=models.PROTECT,
        related_name="return_requests",
        help_text=_(
            "The order this return request is for. "
            "Must be in DELIVERED or RETURN_REQUESTED status when created."
        ),
    )
    requested_by = models.ForeignKey(
        "customers.CustomerProfile",
        verbose_name=_("Requested By"),
        on_delete=models.PROTECT,
        related_name="return_requests",
        help_text=_("Customer who submitted this return request."),
    )
    reason = models.CharField(
        _("Return Reason"),
        max_length=20,
        choices=ReturnReason.choices,
        default=ReturnReason.OTHER,
        db_index=True,
        help_text=_(
            "Top-level reason provided by the customer. "
            "Staff can record a more detailed internal reason on the linked Refund."
        ),
    )
    customer_note = models.TextField(
        _("Customer Note"),
        blank=True,
        help_text=_("Free-text explanation provided by the customer at request time."),
    )
    status = models.CharField(
        _("Status"),
        max_length=15,
        choices=ReturnStatus.choices,
        default=ReturnStatus.PENDING,
        db_index=True,
        help_text=_(
            "Do not update directly. "
            "Use ReturnRequestService which also writes a status history row."
        ),
    )
    reviewed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Reviewed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_return_requests",
        help_text=_("Staff member who approved or rejected this request."),
    )
    staff_note = models.TextField(
        _("Staff Note"),
        blank=True,
        help_text=_(
            "Internal note added by staff during review. Not shown to the customer."
        ),
    )
    # Timestamps for key lifecycle events (set by the service, not auto_now).
    approved_at = models.DateTimeField(_("Approved At"), null=True, blank=True)
    received_at = models.DateTimeField(
        _("Items Received At"),
        null=True,
        blank=True,
        help_text=_("Set when the warehouse confirms all items have been received."),
    )
    completed_at = models.DateTimeField(
        _("Completed At"),
        null=True,
        blank=True,
        help_text=_("Set when the return is fully resolved and refund issued."),
    )

    class Meta:
        verbose_name = _("Return Request")
        verbose_name_plural = _("Return Requests")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["status", "-created"]),
        ]

    def clean(self) -> None:
        super().clean()
        # requested_by must match the order's customer.
        if self.requested_by_id and self.order_id:
            if self.requested_by_id != self.order.customer_id:
                raise ValidationError(
                    {"requested_by": _("The customer must be the owner of the order.")}
                )

    def __str__(self) -> str:
        return f"Return {self.id} - Order {self.order} ({self.get_status_display()})"

    def __repr__(self) -> str:
        return (
            f"<ReturnRequest id={self.id} order={self.order_id} "
            f"status={self.status} reason={self.reason}>"
        )


class ReturnRequestItem(UUIDModel, TimeStampedModel):
    return_request = models.ForeignKey(
        ReturnRequest,
        verbose_name=_("Return Request"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    order_item = models.ForeignKey(
        OrderItem,
        verbose_name=_("Order Item"),
        on_delete=models.PROTECT,
        related_name="return_items",
        help_text=_(
            "The specific order line being returned. "
            "Must belong to the same order as the parent ReturnRequest."
        ),
    )
    quantity_requested = models.PositiveSmallIntegerField(
        _("Quantity Requested"),
        help_text=_(
            "Number of units the customer wants to return. "
            "Must be ≥ 1 and ≤ the original OrderItem.quantity."
        ),
    )
    quantity_received = models.PositiveSmallIntegerField(
        _("Quantity Received"),
        default=0,
        help_text=_(
            "Units actually received and accepted at the warehouse after inspection. "
            "Set by ReturnRequestService.receive(). May differ from quantity_requested "
            "if some items were missing or not accepted."
        ),
    )
    condition_note = models.TextField(
        _("Condition Note"),
        blank=True,
        help_text=_(
            "Warehouse staff note on item condition after inspection, "
            "e.g. 'missing original packaging', 'item not defective - rejected'."
        ),
    )

    class Meta:
        verbose_name = _("Return Request Item")
        verbose_name_plural = _("Return Request Items")
        ordering = ["return_request", "order_item__variant_sku"]
        constraints = [
            # Each order item can appear at most once per return request.
            models.UniqueConstraint(
                fields=["return_request", "order_item"],
                name="unique_return_item_per_request",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_requested__gte=1),
                name="return_item_quantity_requested_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0),
                name="return_item_quantity_received_non_negative",
            ),
            # received can never exceed what was requested.
            models.CheckConstraint(
                condition=models.Q(
                    quantity_received__lte=models.F("quantity_requested")
                ),
                name="return_item_received_lte_requested",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.order_item_id and self.return_request_id:
            # The order item must belong to the same order as the return request.
            if self.order_item.order_id != self.return_request.order_id:
                raise ValidationError(
                    {
                        "order_item": _(
                            "This order item does not belong to the order "
                            "referenced by the return request."
                        )
                    }
                )
            # Cannot request more units than were originally ordered.
            if (
                self.quantity_requested is not None
                and self.quantity_requested > self.order_item.quantity
            ):
                raise ValidationError(
                    {
                        "quantity_requested": _(
                            "Cannot return more units (%(req)s) than were "
                            "originally ordered (%(orig)s)."
                        )
                        % {
                            "req": self.quantity_requested,
                            "orig": self.order_item.quantity,
                        }
                    }
                )

    def __str__(self) -> str:
        return (
            f"{self.order_item.variant_sku} x {self.quantity_requested} "
            f"(return {self.return_request_id})"
        )

    def __repr__(self) -> str:
        return (
            f"<ReturnRequestItem id={self.id} "
            f"return={self.return_request_id} "
            f"sku={self.order_item.variant_sku!r} "
            f"requested={self.quantity_requested} "
            f"received={self.quantity_received}>"
        )


class ReturnShipment(UUIDModel, TimeStampedModel):
    return_request = models.OneToOneField(
        ReturnRequest,
        verbose_name=_("Return Request"),
        on_delete=models.CASCADE,
        related_name="shipment",
        help_text=_(
            "The return request this shipment fulfils. "
            "Create only after the request is APPROVED."
        ),
    )
    tracking_number = models.CharField(
        _("Tracking Number"),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_(
            "Carrier tracking reference provided by the customer. "
            "Set when status transitions to RETURN_SHIPPED."
        ),
    )
    carrier = models.CharField(
        _("Carrier"),
        max_length=100,
        blank=True,
        help_text=_(
            "Carrier name entered by the customer, e.g. 'FedEx', 'DHL', 'Royal Mail'."
        ),
    )
    shipped_at = models.DateTimeField(
        _("Shipped At"),
        null=True,
        blank=True,
        help_text=_("When the customer marked the parcel as dispatched."),
    )
    expected_at = models.DateTimeField(
        _("Expected At"),
        null=True,
        blank=True,
        help_text=_("Estimated arrival date at the warehouse."),
    )
    received_at = models.DateTimeField(
        _("Received At"),
        null=True,
        blank=True,
        help_text=_(
            "When warehouse staff confirmed receipt. "
            "Set by ReturnRequestService.receive()."
        ),
    )
    received_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Received By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_return_shipments",
        help_text=_("Warehouse staff member who processed the incoming parcel."),
    )
    notes = models.TextField(
        _("Notes"),
        blank=True,
        help_text=_(
            "Any additional notes about the shipment, "
            "e.g. packaging condition, partial receipt details."
        ),
    )

    class Meta:
        verbose_name = _("Return Shipment")
        verbose_name_plural = _("Return Shipments")
        ordering = ["-created"]

    def clean(self) -> None:
        super().clean()
        if self.received_at and self.shipped_at and self.received_at < self.shipped_at:
            raise ValidationError(
                {"received_at": _("Received At cannot be earlier than Shipped At.")}
            )

    def __str__(self) -> str:
        tracking = self.tracking_number or "no tracking"
        return f"Return shipment for {self.return_request} - {tracking}"

    def __repr__(self) -> str:
        return (
            f"<ReturnShipment id={self.id} "
            f"return={self.return_request_id} "
            f"tracking={self.tracking_number!r} "
            f"received={self.received_at}>"
        )


class ReturnRequestStatusHistory(StatusHistoryBase):
    return_request = models.ForeignKey(
        ReturnRequest,
        verbose_name=_("Return Request"),
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    # Narrow inherited char fields to return request status choices.
    old_status = models.CharField(
        _("Previous Status"),
        max_length=15,
        choices=ReturnRequestStatusEnum.choices,
        blank=True,
        help_text=_("Empty for the initial (PENDING) entry."),
    )
    new_status = models.CharField(
        _("New Status"),
        max_length=15,
        choices=ReturnRequestStatusEnum.choices,
    )

    class Meta:
        verbose_name = _("Return Request Status History")
        verbose_name_plural = _("Return Request Status Histories")
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return (
            f"Return {self.return_request_id}: "
            f"{self.old_status or '(new)'} -> {self.new_status}"
        )

    def __repr__(self) -> str:
        return (
            f"<ReturnRequestStatusHistory id={self.id} "
            f"return={self.return_request_id} "
            f"{self.old_status!r}->{self.new_status!r}>"
        )
