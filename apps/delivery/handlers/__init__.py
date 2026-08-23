from apps.catalogue.enums import FulfilmentType
from apps.delivery.handlers.digital import AccountProvisionHandler
from apps.delivery.handlers.digital import DownloadHandler
from apps.delivery.handlers.digital import EmailHandler
from apps.delivery.handlers.digital import EventAccessHandler
from apps.delivery.handlers.digital import LicenseKeyHandler
from apps.delivery.handlers.digital import StreamingHandler
from apps.delivery.handlers.digital import SubscriptionHandler
from apps.delivery.handlers.manual import ManualFulfilmentHandler
from apps.delivery.handlers.manual import ServiceAppointmentHandler
from apps.delivery.handlers.physical import LocalDeliveryHandler
from apps.delivery.handlers.physical import ShipmentHandler
from apps.delivery.handlers.physical import StorePickupHandler
from apps.delivery.registry import FulfilmentRoutingRegistry

FulfilmentRoutingRegistry.register(FulfilmentType.SHIPMENT, ShipmentHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.LOCAL_DELIVERY, LocalDeliveryHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.STORE_PICKUP, StorePickupHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.DOWNLOAD, DownloadHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.EMAIL, EmailHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.LICENSE_KEY, LicenseKeyHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.STREAMING, StreamingHandler)
FulfilmentRoutingRegistry.register(
    FulfilmentType.ACCOUNT_PROVISION, AccountProvisionHandler
)
FulfilmentRoutingRegistry.register(FulfilmentType.SUBSCRIPTION, SubscriptionHandler)
FulfilmentRoutingRegistry.register(
    FulfilmentType.SERVICE_APPOINTMENT, ServiceAppointmentHandler
)
FulfilmentRoutingRegistry.register(FulfilmentType.EVENT_ACCESS, EventAccessHandler)
FulfilmentRoutingRegistry.register(FulfilmentType.MANUAL, ManualFulfilmentHandler)

__all__ = [
    "AccountProvisionHandler",
    "DownloadHandler",
    "EmailHandler",
    "EventAccessHandler",
    "LicenseKeyHandler",
    "LocalDeliveryHandler",
    "ManualFulfilmentHandler",
    "ServiceAppointmentHandler",
    "ShipmentHandler",
    "StorePickupHandler",
    "StreamingHandler",
    "SubscriptionHandler",
]
