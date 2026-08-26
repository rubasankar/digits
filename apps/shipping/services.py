"""ShippingService: label generation, shipment creation, tracking ingestion."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import structlog
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.catalogue.enums import FulfilmentType
from apps.delivery.models import Fulfilment
from apps.delivery.services import FulfilmentService
from apps.shipping.exceptions import ShippingServiceError
from apps.shipping.models import Shipment
from apps.shipping.models import ShippingMethod
from apps.shipping.models import TrackingEvent

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


logger = structlog.get_logger(__name__)

# Fulfilment types that hand off to a carrier. STORE_PICKUP is physical but
# is handled by delivery alone -- it never reaches this app.
CARRIER_FULFILMENT_TYPES: frozenset[str] = frozenset(
    {
        FulfilmentType.SHIPMENT,
        FulfilmentType.LOCAL_DELIVERY,
    }
)


class ShippingService:
    """Handles carrier label generation, shipment records, and tracking ingestion."""

    @classmethod
    def request_label(
        cls,
        fulfilment_id: uuid.UUID,
        shipping_method_id: uuid.UUID,
    ) -> None:
        """Request a carrier label for a physical-group Fulfilment."""

        fulfilment = Fulfilment.objects.select_related(
            "order_item__order",
            "warehouse",
        ).get(pk=fulfilment_id)

        if fulfilment.fulfilment_type not in CARRIER_FULFILMENT_TYPES:
            msg = (
                f"Cannot request label for non-carrier "
                f"fulfilment type '{fulfilment.fulfilment_type}'."
            )
            raise ValueError(msg)

        shipping_method = ShippingMethod.objects.select_related("carrier").get(
            pk=shipping_method_id
        )

        shipment = Shipment.objects.create(
            fulfilment=fulfilment,
            shipping_method=shipping_method,
            label_generated_at=None,
        )
        logger.info(
            "shipping.request_label.shipment_created",
            fulfilment_id=str(fulfilment_id),
            shipment_id=str(shipment.pk),
        )

        try:
            cls._call_carrier_api(shipment, shipping_method)
        except ShippingServiceError as exc:
            shipment.label_error = str(exc)
            shipment.save(update_fields=["label_error"])
            logger.warning(
                "shipping.request_label.carrier_api_failed",
                fulfilment_id=str(fulfilment_id),
                shipment_id=str(shipment.pk),
                error=str(exc),
            )
            return

        # Success path (reached only if _call_carrier_api is implemented).
        now = timezone.now()
        tracking_number: str = shipment.tracking_number
        carrier_name: str = (
            shipping_method.carrier.name if shipping_method.carrier else ""
        )
        shipment.label_generated_at = now
        shipment.save(
            update_fields=["label_generated_at", "tracking_number", "label_url"]
        )

        # The fulfilment was already moved to SHIPPED by the transition() call
        # that triggered this dispatch (see FulfilmentService._dispatch_handler);
        # SHIPPED -> SHIPPED isn't a valid transition, so backfill the
        # carrier-provided details as a plain field update, not another
        # transition.
        fulfilment.tracking_number = tracking_number
        fulfilment.carrier = carrier_name
        fulfilment.save(update_fields=["tracking_number", "carrier", "modified"])

        logger.info(
            "shipping.request_label.shipped",
            fulfilment_id=str(fulfilment_id),
            tracking_number=tracking_number,
        )

    @classmethod
    def ingest_tracking_event(
        cls,
        tracking_number: str,
        event_code: str,
        event_timestamp: datetime,
        raw_payload: dict[str, Any],
    ) -> TrackingEvent | None:
        """Ingest a carrier tracking event and advance Fulfilment if delivered."""
        try:
            shipment = Shipment.objects.select_related(
                "fulfilment",
            ).get(tracking_number=tracking_number)
        except Shipment.DoesNotExist as exc:
            msg = f"No shipment found for tracking number '{tracking_number}'."
            raise ShippingServiceError(msg) from exc

        fulfilment: Fulfilment = shipment.fulfilment

        if fulfilment.fulfilment_type == FulfilmentType.STORE_PICKUP:
            msg = (
                "Cannot ingest tracking events for STORE_PICKUP fulfilments; "
                "completion is confirmed by staff scan."
            )
            raise ValueError(msg)

        try:
            event = TrackingEvent.objects.create(
                shipment=shipment,
                event_code=event_code,
                event_timestamp=event_timestamp,
                raw_payload=raw_payload,
            )
        except IntegrityError:
            logger.info(
                "shipping.ingest_tracking_event.duplicate_ignored",
                tracking_number=tracking_number,
                event_code=event_code,
            )
            return None

        delivered_codes: frozenset[str] = frozenset(
            getattr(
                settings,
                "SHIPPING_DELIVERED_EVENT_CODES",
                {"DELIVERED", "DEL", "POD"},
            )
        )
        if event_code in delivered_codes:
            FulfilmentService.deliver(fulfilment)
            logger.info(
                "shipping.ingest_tracking_event.delivered",
                tracking_number=tracking_number,
                fulfilment_id=str(fulfilment.pk),
            )

        return event

    # stubs

    @classmethod
    def _call_carrier_api(
        cls,
        shipment: Shipment,
        shipping_method: ShippingMethod,
    ) -> None:
        """Stub: call carrier API to generate a label. Not yet implemented."""
        msg = "Carrier API not yet implemented."
        raise ShippingServiceError(msg)
