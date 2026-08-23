from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils.models import TimeStampedModel
from model_utils.models import UUIDModel

from apps.catalogue.enums import FulfilmentType
from apps.delivery.enums import FulfilmentStatusEnum


class Fulfilment(UUIDModel, TimeStampedModel):
    order_item = models.OneToOneField(
        "orders.OrderItem",
        verbose_name=_("Order Item"),
        on_delete=models.CASCADE,
        related_name="fulfilment",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        verbose_name=_("Warehouse"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fulfilments",
        help_text=_("Null for non-physical fulfilment types."),
    )
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=FulfilmentStatusEnum.choices,
        default=FulfilmentStatusEnum.PENDING,
        db_index=True,
    )
    fulfilment_type = models.CharField(
        _("Fulfilment Type"),
        max_length=25,
        choices=FulfilmentType.choices,
        db_index=True,
        help_text=_(
            "Copied from Product.fulfilment_type at order placement. "
            "Determines which handler the routing registry dispatches to."
        ),
    )
    tracking_number = models.CharField(
        _("Tracking Number"),
        max_length=255,
        blank=True,
    )
    carrier = models.CharField(
        _("Carrier"),
        max_length=100,
        blank=True,
    )
    dispatch_error = models.TextField(
        _("Dispatch Error"),
        blank=True,
    )
    allocated_at = models.DateTimeField(_("Allocated At"), null=True, blank=True)
    picked_at = models.DateTimeField(_("Picked At"), null=True, blank=True)
    packed_at = models.DateTimeField(_("Packed At"), null=True, blank=True)
    shipped_at = models.DateTimeField(_("Shipped At"), null=True, blank=True)
    delivered_at = models.DateTimeField(_("Delivered At"), null=True, blank=True)

    class Meta:
        verbose_name = _("Fulfilment")
        verbose_name_plural = _("Fulfilments")
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"Fulfilment {self.id} [{self.status}]"

    def __repr__(self) -> str:
        return (
            f"<Fulfilment id={self.id} "
            f"order_item={self.order_item_id} "
            f"type={self.fulfilment_type} "
            f"status={self.status}>"
        )


class FulfilmentStatusHistory(UUIDModel):
    fulfilment = models.ForeignKey(
        Fulfilment,
        verbose_name=_("Fulfilment"),
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(
        _("Previous Status"),
        max_length=10,
        choices=FulfilmentStatusEnum.choices,
        blank=True,
        help_text=_("Empty for the initial PENDING row."),
    )
    new_status = models.CharField(
        _("New Status"),
        max_length=10,
        choices=FulfilmentStatusEnum.choices,
    )
    changed_by = models.ForeignKey(
        "staff.StaffProfile",
        verbose_name=_("Changed By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fulfilment_status_changes",
        help_text=_("Null for system-triggered transitions."),
    )
    note = models.TextField(_("Note"), blank=True)
    changed_at = models.DateTimeField(_("Changed At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Fulfilment Status History")
        verbose_name_plural = _("Fulfilment Status Histories")
        ordering = ["changed_at"]

    def __str__(self) -> str:
        return (
            f"Fulfilment {self.fulfilment_id}: "
            f"{self.old_status or '(new)'} -> {self.new_status}"
        )

    def __repr__(self) -> str:
        return (
            f"<FulfilmentStatusHistory id={self.id} "
            f"fulfilment={self.fulfilment_id} "
            f"{self.old_status!r}->{self.new_status!r}>"
        )
