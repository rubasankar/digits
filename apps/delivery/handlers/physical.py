from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import structlog

from apps.delivery.registry import FulfilmentHandler
from apps.shipping.models import ShippingMethod
from apps.shipping.services import ShippingService

if TYPE_CHECKING:
    import uuid

    from apps.delivery.models import Fulfilment

logger = structlog.get_logger(__name__)


class PhysicalHandoffHandler(FulfilmentHandler):
    """Abstract base for all physical handoff fulfilment types."""

    @abstractmethod
    def dispatch(self, fulfilment: Fulfilment) -> None: ...


class ShipmentHandler(PhysicalHandoffHandler):
    """Handles SHIPMENT fulfilments - requests a carrier label via ShippingService."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Request a carrier label for a standard shipment."""

        order = fulfilment.order_item.order
        checkout = order.checkout_session
        # checkout_session.shipping_method stores the method name/code, so resolve
        # it to the ShippingMethod primary key expected by ShippingService.
        shipping_method_name: str = checkout.shipping_method
        shipping_method_id: uuid.UUID = (
            ShippingMethod.objects.only("pk").get(name=shipping_method_name).pk
        )

        logger.info(
            "delivery.shipment_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
            shipping_method=shipping_method_name,
        )
        ShippingService.request_label(fulfilment.pk, shipping_method_id)


class LocalDeliveryHandler(PhysicalHandoffHandler):
    """Handles LOCAL_DELIVERY fulfilments - requests a label via ShippingService."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Request a carrier label for a local delivery fulfilment."""

        order = fulfilment.order_item.order
        checkout = order.checkout_session
        # checkout_session.shipping_method stores the method name/code, so resolve
        # it to the ShippingMethod primary key expected by ShippingService.
        shipping_method_name: str = checkout.shipping_method
        shipping_method_id: uuid.UUID = (
            ShippingMethod.objects.only("pk").get(name=shipping_method_name).pk
        )

        logger.info(
            "delivery.local_delivery_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
            shipping_method=shipping_method_name,
        )
        ShippingService.request_label(fulfilment.pk, shipping_method_id)


class StorePickupHandler(PhysicalHandoffHandler):
    """
    Handles STORE_PICKUP fulfilments entirely within delivery.

    Store pickup never touches a carrier, so unlike ShipmentHandler and
    LocalDeliveryHandler it does not call into the shipping app at all --
    Fulfilment.status/shipped_at (stamped by the transition that triggered
    this dispatch) fully represent "ready for pickup"; FulfilmentService.
    deliver() (triggered by staff confirming the handoff at the counter)
    represents "picked up".
    """

    def dispatch(self, fulfilment: Fulfilment) -> None:
        logger.info(
            "delivery.store_pickup_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
