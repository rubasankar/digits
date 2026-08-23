from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import structlog
from django.conf import settings

from apps.delivery.registry import FulfilmentHandler

if TYPE_CHECKING:
    from apps.delivery.models import Fulfilment

logger = structlog.get_logger(__name__)

_DEFAULT_DOWNLOAD_EXPIRY_HOURS: int = 48


class DigitalHandler(FulfilmentHandler):
    """Abstract base for all digital/automated fulfilment types."""

    @abstractmethod
    def dispatch(self, fulfilment: Fulfilment) -> None: ...


class DownloadHandler(DigitalHandler):
    """Handles DOWNLOAD fulfilments - generates a signed, time-limited download URL."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Generate a signed download URL and deliver via the notification service."""
        expiry_hours: int = getattr(
            settings, "DOWNLOAD_LINK_EXPIRY_HOURS", _DEFAULT_DOWNLOAD_EXPIRY_HOURS
        )
        logger.info(
            "delivery.download_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
            expiry_hours=expiry_hours,
        )
        # Stub: DownloadService.generate_signed_url is not yet implemented.
        msg = (
            "DownloadService.generate_signed_url is not yet implemented. "
            "Implement apps.downloads.services.DownloadService and wire it here."
        )
        raise NotImplementedError(msg)


class EmailHandler(DigitalHandler):
    """Handles EMAIL fulfilments - dispatches content to the customer via email."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Dispatch the digital content to the customer via email service."""
        logger.info(
            "delivery.email_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: EmailDeliveryService is not yet implemented.
        msg = (
            "EmailDeliveryService is not yet implemented. "
            "Implement apps.notifications.services.EmailDeliveryService"
            " and wire it here."
        )
        raise NotImplementedError(msg)


class LicenseKeyHandler(DigitalHandler):
    """Handles LICENSE_KEY fulfilments - generates/activates a key and delivers it."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Generate or activate a license key and deliver via notification service."""
        logger.info(
            "delivery.license_key_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: LicenseService is not yet implemented.
        msg = (
            "LicenseService is not yet implemented. "
            "Implement apps.licenses.services.LicenseService and wire it here."
        )
        raise NotImplementedError(msg)


class StreamingHandler(DigitalHandler):
    """Handles STREAMING fulfilments - provisions streaming access for the customer."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Invoke the external streaming API to provision access for this order item."""
        logger.info(
            "delivery.streaming_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: StreamingProvisioningService is not yet implemented.
        msg = (
            "StreamingProvisioningService is not yet implemented. "
            "Implement the relevant external API integration and wire it here."
        )
        raise NotImplementedError(msg)


class AccountProvisionHandler(DigitalHandler):
    """Handles ACCOUNT_PROVISION fulfilments - provisions a customer account."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Invoke the internal account provisioning hook for this order item."""
        logger.info(
            "delivery.account_provision_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: AccountProvisioningService is not yet implemented.
        msg = (
            "AccountProvisioningService is not yet implemented. "
            "Implement the relevant provisioning hook and wire it here."
        )
        raise NotImplementedError(msg)


class SubscriptionHandler(DigitalHandler):
    """Handles SUBSCRIPTION fulfilments - activates a recurring subscription."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Invoke the subscription provisioning hook for this order item."""
        logger.info(
            "delivery.subscription_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: SubscriptionService is not yet implemented.
        msg = (
            "SubscriptionService is not yet implemented. "
            "Implement the relevant subscription provisioning and wire it here."
        )
        raise NotImplementedError(msg)


class EventAccessHandler(DigitalHandler):
    """Handles EVENT_ACCESS fulfilments - generates a ticket/QR code for the event."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Generate a ticket or QR code and deliver it via the notification service."""
        logger.info(
            "delivery.event_access_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
        )
        # Stub: EventTicketService is not yet implemented.
        msg = (
            "EventTicketService is not yet implemented. "
            "Implement apps.events.services.EventTicketService and wire it here."
        )
        raise NotImplementedError(msg)
