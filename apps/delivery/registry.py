from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

from django.core.exceptions import ImproperlyConfigured

from apps.catalogue.enums import FulfilmentType
from apps.delivery.exceptions import UnregisteredFulfilmentTypeError

if TYPE_CHECKING:
    from apps.delivery.models import Fulfilment


class FulfilmentHandler(ABC):
    """Abstract base class for all fulfilment type handlers."""

    @abstractmethod
    def dispatch(self, fulfilment: Fulfilment) -> None:
        """Called by FulfilmentService after every successful SHIPPED transition."""
        ...


class FulfilmentRoutingRegistry:
    """Maps each FulfilmentType value to its FulfilmentHandler subclass."""

    _registry: dict[str, type[FulfilmentHandler]] = {}

    @classmethod
    def register(
        cls,
        fulfilment_type: str,
        handler_class: type[FulfilmentHandler],
    ) -> None:
        """Register a handler class for a given fulfilment type string."""
        cls._registry[fulfilment_type] = handler_class

    @classmethod
    def get_handler(cls, fulfilment_type: str) -> type[FulfilmentHandler]:
        """Look up and return the registered handler class for fulfilment_type."""
        try:
            return cls._registry[fulfilment_type]
        except KeyError as exc:
            msg = f"No handler registered for FulfilmentType '{fulfilment_type}'"
            raise UnregisteredFulfilmentTypeError(msg) from exc

    @classmethod
    def assert_complete(cls) -> None:
        """Raise ImproperlyConfigured if any FulfilmentType value lacks a handler."""
        missing = [ft for ft in FulfilmentType.values if ft not in cls._registry]
        if missing:
            msg = (
                f"FulfilmentRoutingRegistry is incomplete. "
                f"Missing handlers for: {missing}"
            )
            raise ImproperlyConfigured(msg)
