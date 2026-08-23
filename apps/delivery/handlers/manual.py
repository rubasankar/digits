from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

import structlog

from apps.delivery.registry import FulfilmentHandler

if TYPE_CHECKING:
    from apps.delivery.models import Fulfilment

logger = structlog.get_logger(__name__)


class ManualHandlerBase(FulfilmentHandler):
    """Abstract base for all manual fulfilment types requiring staff action."""

    @abstractmethod
    def dispatch(self, fulfilment: Fulfilment) -> None: ...


class ServiceAppointmentHandler(ManualHandlerBase):
    """Handles SERVICE_APPOINTMENT fulfilments - books an appointment and notifies."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Create a service appointment booking and notify customer and service team."""
        # Stub: ServiceAppointmentService is not yet implemented.
        # When the appointments feature is built, replace this log call with a
        # proper booking record creation and notification dispatch.
        logger.info(
            "delivery.service_appointment_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
            order_item_id=str(fulfilment.order_item_id),
            message=(
                "Service appointment booking stub invoked. "
                "Implement ServiceAppointmentService to create a booking record "
                "and notify the customer and service team."
            ),
        )


class ManualFulfilmentHandler(ManualHandlerBase):
    """Handles MANUAL fulfilments - marks the fulfilment awaiting staff action."""

    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Create a staff task record marking this fulfilment as awaiting action."""
        # Stub: StaffTaskService is not yet implemented.
        # When the staff tasks feature is built, replace this log call with a
        # proper staff task record creation.
        logger.info(
            "delivery.manual_fulfilment_handler.dispatch",
            fulfilment_id=str(fulfilment.pk),
            order_item_id=str(fulfilment.order_item_id),
            message=(
                "Manual fulfilment staff task stub invoked. "
                "Implement StaffTaskService to create a staff task record "
                "and notify the assigned staff member."
            ),
        )
