from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from functools import partial
from typing import TYPE_CHECKING

import structlog
from django.db import transaction
from django.utils import timezone

from apps.catalogue.enums import FulfilmentType
from apps.delivery.enums import FulfilmentStatusEnum
from apps.delivery.exceptions import InvalidStatusTransitionError
from apps.delivery.exceptions import MissingShipmentInfoError
from apps.delivery.models import Fulfilment
from apps.delivery.models import FulfilmentStatusHistory
from apps.delivery.registry import FulfilmentRoutingRegistry
from apps.inventory.services import StockMovementService
from apps.orders.enums import OrderStatusEnum
from apps.orders.service.order import OrderService

if TYPE_CHECKING:
    import uuid

    from apps.inventory.models import Warehouse
    from apps.orders.models import OrderItem
    from apps.staff.models import StaffProfile

logger = structlog.get_logger(__name__)

# Physical-group types - require warehouse, trigger stock side-effects.
PHYSICAL_FULFILMENT_TYPES: frozenset[str] = frozenset(
    {
        FulfilmentType.SHIPMENT,
        FulfilmentType.LOCAL_DELIVERY,
        FulfilmentType.STORE_PICKUP,
    }
)

# Allowed status transitions.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    FulfilmentStatusEnum.PENDING: frozenset(
        {FulfilmentStatusEnum.ALLOCATED, FulfilmentStatusEnum.CANCELLED}
    ),
    FulfilmentStatusEnum.ALLOCATED: frozenset(
        {FulfilmentStatusEnum.PICKED, FulfilmentStatusEnum.CANCELLED}
    ),
    FulfilmentStatusEnum.PICKED: frozenset({FulfilmentStatusEnum.PACKED}),
    FulfilmentStatusEnum.PACKED: frozenset({FulfilmentStatusEnum.SHIPPED}),
    FulfilmentStatusEnum.SHIPPED: frozenset({FulfilmentStatusEnum.DELIVERED}),
    FulfilmentStatusEnum.DELIVERED: frozenset(),
    FulfilmentStatusEnum.CANCELLED: frozenset(),
}

# Milestone timestamp field stamped for each forward transition.
_TRANSITION_TIMESTAMPS: dict[str, str] = {
    FulfilmentStatusEnum.ALLOCATED: "allocated_at",
    FulfilmentStatusEnum.PICKED: "picked_at",
    FulfilmentStatusEnum.PACKED: "packed_at",
    FulfilmentStatusEnum.SHIPPED: "shipped_at",
    FulfilmentStatusEnum.DELIVERED: "delivered_at",
}

# Pre-terminal statuses: cancellation from these triggers reservation release.
_PRE_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        FulfilmentStatusEnum.PENDING,
        FulfilmentStatusEnum.ALLOCATED,
        FulfilmentStatusEnum.PICKED,
        FulfilmentStatusEnum.PACKED,
    }
)


@dataclass(frozen=True, slots=True)
class ShipmentInfo:
    """Carrier details recorded when a fulfilment ships."""

    tracking_number: str = field(default="")
    carrier: str = field(default="")


class FulfilmentService:
    """Manages the lifecycle of Fulfilment records in the delivery layer."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        order_item: OrderItem,
        warehouse: Warehouse | None,
        fulfilment_type: str,
    ) -> Fulfilment:
        """Create a PENDING Fulfilment and write the initial history row."""
        if fulfilment_type in PHYSICAL_FULFILMENT_TYPES and warehouse is None:
            msg = (
                "A warehouse is required for physical"
                f" fulfilment type '{fulfilment_type}'."
            )
            raise ValueError(msg)

        fulfilment = Fulfilment(
            order_item=order_item,
            warehouse=warehouse,
            fulfilment_type=fulfilment_type,
            status=FulfilmentStatusEnum.PENDING,
        )
        fulfilment.full_clean()
        fulfilment.save()

        FulfilmentStatusHistory.objects.create(
            fulfilment=fulfilment,
            old_status="",
            new_status=FulfilmentStatusEnum.PENDING,
        )

        return fulfilment

    @classmethod
    def transition(
        cls,
        fulfilment: Fulfilment,
        new_status: str,
        *,
        changed_by: StaffProfile | None,
        note: str | None = None,
        shipment_info: ShipmentInfo | None = None,
    ) -> Fulfilment:
        """Advance fulfilment to new_status; write history and fire side-effects."""
        cls._validate_transition(fulfilment, new_status, shipment_info)

        old_status = fulfilment.status
        is_physical = fulfilment.fulfilment_type in PHYSICAL_FULFILMENT_TYPES
        fulfilment_id: uuid.UUID = fulfilment.pk

        with transaction.atomic():
            cls._apply_transition(fulfilment, new_status, shipment_info)
            FulfilmentStatusHistory.objects.create(
                fulfilment=fulfilment,
                old_status=old_status,
                new_status=new_status,
                changed_by=changed_by,
                note=note or "",
            )
            if new_status == FulfilmentStatusEnum.SHIPPED:
                cls._dispatch_handler(fulfilment)
            if new_status == FulfilmentStatusEnum.DELIVERED:
                cls._maybe_deliver_order(fulfilment)

        cls._schedule_post_commit_hooks(
            fulfilment_id=fulfilment_id,
            new_status=new_status,
            old_status=old_status,
            is_physical=is_physical,
        )

        return fulfilment

    @classmethod
    def ship(
        cls,
        fulfilment: Fulfilment,
        *,
        tracking_number: str = "",
        carrier: str = "",
        changed_by: StaffProfile | None = None,
    ) -> Fulfilment:
        """Convenience wrapper: transition to SHIPPED with carrier details."""
        return cls.transition(
            fulfilment,
            FulfilmentStatusEnum.SHIPPED,
            changed_by=changed_by,
            shipment_info=ShipmentInfo(
                tracking_number=tracking_number,
                carrier=carrier,
            ),
        )

    @classmethod
    def deliver(cls, fulfilment: Fulfilment) -> None:
        """Transition to DELIVERED; silently skip already-terminal fulfilments."""
        if fulfilment.status in {
            FulfilmentStatusEnum.DELIVERED,
            FulfilmentStatusEnum.CANCELLED,
        }:
            return
        cls.transition(fulfilment, FulfilmentStatusEnum.DELIVERED, changed_by=None)

    @classmethod
    def cancel(
        cls,
        fulfilment: Fulfilment,
        *,
        changed_by: StaffProfile | None = None,
    ) -> Fulfilment:
        """Transition to CANCELLED."""
        return cls.transition(
            fulfilment,
            FulfilmentStatusEnum.CANCELLED,
            changed_by=changed_by,
        )

    # private

    @staticmethod
    def _validate_transition(
        fulfilment: Fulfilment,
        new_status: str,
        shipment_info: ShipmentInfo | None,
    ) -> None:
        """Raise before any DB write if the transition is not allowed."""
        allowed = ALLOWED_TRANSITIONS.get(fulfilment.status, frozenset())
        if new_status not in allowed:
            msg = (
                f"Fulfilment cannot transition from"
                f" '{fulfilment.status}' to '{new_status}'."
            )
            raise InvalidStatusTransitionError(msg)
        is_physical = fulfilment.fulfilment_type in PHYSICAL_FULFILMENT_TYPES
        if (
            is_physical
            and new_status == FulfilmentStatusEnum.SHIPPED
            and shipment_info is None
        ):
            msg = "shipment_info is required when shipping a physical-group fulfilment."
            raise MissingShipmentInfoError(msg)

    @staticmethod
    def _apply_transition(
        fulfilment: Fulfilment,
        new_status: str,
        shipment_info: ShipmentInfo | None,
    ) -> None:
        """Write status, timestamp, and shipment fields to the Fulfilment row."""
        update_fields: list[str] = ["status", "modified"]
        now = timezone.now()

        timestamp_field = _TRANSITION_TIMESTAMPS.get(new_status)
        if timestamp_field is not None:
            setattr(fulfilment, timestamp_field, now)
            update_fields.append(timestamp_field)

        if new_status == FulfilmentStatusEnum.SHIPPED and shipment_info is not None:
            if shipment_info.tracking_number:
                fulfilment.tracking_number = shipment_info.tracking_number
                update_fields.append("tracking_number")
            if shipment_info.carrier:
                fulfilment.carrier = shipment_info.carrier
                update_fields.append("carrier")

        fulfilment.status = new_status
        fulfilment.save(update_fields=update_fields)

    @staticmethod
    def _dispatch_handler(fulfilment: Fulfilment) -> None:
        """Instantiate and call the registered handler for SHIPPED transition."""
        handler_class = FulfilmentRoutingRegistry.get_handler(
            fulfilment.fulfilment_type
        )
        handler_class().dispatch(fulfilment)

    @staticmethod
    def _maybe_deliver_order(fulfilment: Fulfilment) -> None:
        """Transition the parent order to DELIVERED if all items are now DELIVERED."""
        order = fulfilment.order_item.order
        sibling_statuses = list(
            Fulfilment.objects.filter(order_item__order=order).values_list(
                "status", flat=True
            )
        )
        if not sibling_statuses:
            return
        if all(s == FulfilmentStatusEnum.DELIVERED for s in sibling_statuses):
            OrderService.transition(order, OrderStatusEnum.DELIVERED)

    @classmethod
    def _schedule_post_commit_hooks(
        cls,
        *,
        fulfilment_id: uuid.UUID,
        new_status: str,
        old_status: str,
        is_physical: bool,
    ) -> None:
        """Register on_commit callbacks for stock side-effects."""
        if is_physical and new_status == FulfilmentStatusEnum.SHIPPED:
            transaction.on_commit(
                partial(cls._post_commit_stock_effects, fulfilment_id=fulfilment_id)
            )

        if (
            is_physical
            and new_status == FulfilmentStatusEnum.CANCELLED
            and old_status in _PRE_TERMINAL_STATUSES
        ):
            transaction.on_commit(
                partial(
                    cls._post_commit_release_reservation,
                    fulfilment_id=fulfilment_id,
                )
            )

    @classmethod
    def _post_commit_stock_effects(cls, *, fulfilment_id: uuid.UUID) -> None:
        """Release reservation then record sale after a SHIPPED commit."""
        try:
            fulfilment = Fulfilment.objects.select_related(
                "order_item__variant",
                "warehouse",
            ).get(pk=fulfilment_id)
        except Fulfilment.DoesNotExist:
            logger.exception(
                "delivery.post_commit_stock_effects.not_found",
                fulfilment_id=str(fulfilment_id),
            )
            return

        item = fulfilment.order_item
        if item.variant is None:
            logger.warning(
                "delivery.post_commit_stock_effects.variant_deleted",
                fulfilment_id=str(fulfilment_id),
            )
            return

        if fulfilment.warehouse is None:
            logger.warning(
                "delivery.post_commit_stock_effects.no_warehouse",
                fulfilment_id=str(fulfilment_id),
            )
            return

        try:
            StockMovementService.release_reservation(
                variant=item.variant,
                warehouse=fulfilment.warehouse,
                quantity=item.quantity,
                order_item=item,
            )
        except Exception:
            logger.exception(
                "delivery.post_commit_stock_effects.release_failed",
                fulfilment_id=str(fulfilment_id),
            )
            return

        try:
            StockMovementService.record_sale(
                variant=item.variant,
                warehouse=fulfilment.warehouse,
                quantity=item.quantity,
                order_item=item,
            )
        except Exception:
            logger.exception(
                "delivery.post_commit_stock_effects.sale_failed",
                fulfilment_id=str(fulfilment_id),
            )

    @classmethod
    def _post_commit_release_reservation(cls, *, fulfilment_id: uuid.UUID) -> None:
        """Release stock reservation after a CANCELLED commit."""
        try:
            fulfilment = Fulfilment.objects.select_related(
                "order_item__variant",
                "warehouse",
            ).get(pk=fulfilment_id)
        except Fulfilment.DoesNotExist:
            logger.exception(
                "delivery.post_commit_release_reservation.not_found",
                fulfilment_id=str(fulfilment_id),
            )
            return

        item = fulfilment.order_item
        if item.variant is None:
            logger.warning(
                "delivery.post_commit_release_reservation.variant_deleted",
                fulfilment_id=str(fulfilment_id),
            )
            return

        if fulfilment.warehouse is None:
            logger.warning(
                "delivery.post_commit_release_reservation.no_warehouse",
                fulfilment_id=str(fulfilment_id),
            )
            return

        try:
            StockMovementService.release_reservation(
                variant=item.variant,
                warehouse=fulfilment.warehouse,
                quantity=item.quantity,
                order_item=item,
            )
        except Exception:
            logger.exception(
                "delivery.post_commit_release_reservation.release_failed",
                fulfilment_id=str(fulfilment_id),
            )
