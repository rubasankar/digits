from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel


class CarrierAccount(UUIDModel, TimeStampedModel):
    """Represents an external carrier integration account."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    carrier_code = models.CharField(_("Carrier Code"), max_length=30, unique=True)
    is_active = models.BooleanField(_("Is Active"), default=True)
    credentials = models.JSONField(
        _("Credentials"),
        default=dict,
        help_text=_(
            "API keys, endpoint URLs, and carrier-specific config. "
            "Values are encrypted at rest via the field's storage backend."
        ),
    )

    class Meta:
        verbose_name = _("Carrier Account")
        verbose_name_plural = _("Carrier Accounts")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<CarrierAccount id={self.id} code={self.carrier_code!r}>"


class ShippingMethod(UUIDModel, TimeStampedModel):
    """Catalogue entry for a carrier shipping service tier."""

    name = models.CharField(_("Name"), max_length=100, unique=True)
    carrier = models.ForeignKey(
        CarrierAccount,
        verbose_name=_("Carrier Account"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shipping_methods",
    )
    is_active = models.BooleanField(_("Is Active"), default=True)
    estimated_days_min = models.PositiveSmallIntegerField(
        _("Estimated Days (Min)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    estimated_days_max = models.PositiveSmallIntegerField(
        _("Estimated Days (Max)"),
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
    )
    base_rate = models.DecimalField(
        _("Base Rate"),
        max_digits=12,
        decimal_places=4,
        default=0,
    )
    currency = models.ForeignKey(
        "pricing.Currency",
        verbose_name=_("Currency"),
        on_delete=models.PROTECT,
        related_name="shipping_methods",
    )
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Shipping Method")
        verbose_name_plural = _("Shipping Methods")
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(estimated_days_min__isnull=True)
                    | models.Q(estimated_days_max__isnull=True)
                    | models.Q(estimated_days_min__lte=models.F("estimated_days_max"))
                ),
                name="shipping_method_days_min_lte_max",
            ),
            models.CheckConstraint(
                condition=models.Q(base_rate__gte=0),
                name="shipping_method_base_rate_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<ShippingMethod id={self.id} name={self.name!r}>"


class Shipment(UUIDModel, TimeStampedModel):
    """Physical dispatch record linking a Fulfilment to a carrier label."""

    fulfilment = models.OneToOneField(
        "delivery.Fulfilment",
        verbose_name=_("Fulfilment"),
        on_delete=models.PROTECT,
        related_name="shipment",
    )
    shipping_method = models.ForeignKey(
        ShippingMethod,
        verbose_name=_("Shipping Method"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="shipments",
    )
    tracking_number = models.CharField(
        _("Tracking Number"),
        max_length=100,
        blank=True,
        db_index=True,
    )
    label_url = models.URLField(_("Label URL"), max_length=500, blank=True)
    label_data = models.BinaryField(_("Label Data"), blank=True)
    requested_at = models.DateTimeField(_("Requested At"), auto_now_add=True)
    label_generated_at = models.DateTimeField(
        _("Label Generated At"),
        null=True,
        blank=True,
    )
    carrier_reference = models.CharField(
        _("Carrier Reference"),
        max_length=100,
        blank=True,
    )
    label_error = models.TextField(
        _("Label Error"),
        blank=True,
        help_text=_("Set when label generation fails. Cleared on successful retry."),
    )

    class Meta:
        verbose_name = _("Shipment")
        verbose_name_plural = _("Shipments")
        ordering = ["-requested_at"]
        constraints = [
            # Blank tracking_number is normal pre-label (multiple rows can be
            # blank at once); once a real tracking number is set it must be
            # unique so ingest_tracking_event() can look one up unambiguously.
            models.UniqueConstraint(
                fields=["tracking_number"],
                condition=~models.Q(tracking_number=""),
                name="unique_shipment_tracking_number",
            ),
        ]

    def __str__(self) -> str:
        return f"Shipment {self.id} [{self.tracking_number or 'no tracking'}]"

    def __repr__(self) -> str:
        return (
            f"<Shipment id={self.id} "
            f"fulfilment={self.fulfilment_id} "
            f"tracking={self.tracking_number!r}>"
        )


class TrackingEvent(UUIDModel):
    """Individual carrier status event ingested from a tracking webhook."""

    shipment = models.ForeignKey(
        Shipment,
        verbose_name=_("Shipment"),
        on_delete=models.CASCADE,
        related_name="tracking_events",
    )
    event_code = models.CharField(_("Event Code"), max_length=30)
    event_timestamp = models.DateTimeField(_("Event Timestamp"))
    description = models.TextField(_("Description"), blank=True)
    raw_payload = models.JSONField(_("Raw Payload"), default=dict)

    class Meta:
        verbose_name = _("Tracking Event")
        verbose_name_plural = _("Tracking Events")
        ordering = ["event_timestamp"]
        constraints = [
            models.UniqueConstraint(
                fields=["shipment", "event_code", "event_timestamp"],
                name="unique_tracking_event_per_shipment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_code} @ {self.event_timestamp}"

    def __repr__(self) -> str:
        return (
            f"<TrackingEvent id={self.id} "
            f"shipment={self.shipment_id} "
            f"code={self.event_code!r}>"
        )
