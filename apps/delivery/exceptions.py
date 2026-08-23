class InvalidStatusTransitionError(Exception):
    """Raised when a requested fulfilment status transition is not permitted."""


class MissingShipmentInfoError(Exception):
    """Raised when shipment info is required but not provided for SHIPPED transition."""


class WarehouseResolutionError(Exception):
    """Raised when no warehouse can be resolved for a physical-group fulfilment line."""


class UnregisteredFulfilmentTypeError(Exception):
    """Raised when a fulfilment type has no handler in the routing registry."""
