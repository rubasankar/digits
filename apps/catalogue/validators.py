from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .constants import SKU_MAX_LENGTH
from .enums import UNITS_BY_DIMENSION
from .enums import FulfilmentType
from .enums import ProductType
from .enums import UnitDimension

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_VALID_FULFILMENT: dict[str, frozenset[str]] = {
    ProductType.DIGITAL: frozenset(
        {
            FulfilmentType.DOWNLOAD,
            FulfilmentType.EMAIL,
            FulfilmentType.LICENSE_KEY,
            FulfilmentType.STREAMING,
        }
    ),
    ProductType.SUBSCRIPTION: frozenset(
        {
            FulfilmentType.SUBSCRIPTION,
            FulfilmentType.ACCOUNT_PROVISION,
            FulfilmentType.STREAMING,
        }
    ),
    ProductType.SERVICE: frozenset(
        {
            FulfilmentType.SERVICE_APPOINTMENT,
            FulfilmentType.MANUAL,
            FulfilmentType.LOCAL_DELIVERY,
        }
    ),
    ProductType.EVENT: frozenset(
        {
            FulfilmentType.EVENT_ACCESS,
            FulfilmentType.EMAIL,
            FulfilmentType.DOWNLOAD,
        }
    ),
    ProductType.COURSE: frozenset(
        {
            FulfilmentType.STREAMING,
            FulfilmentType.DOWNLOAD,
            FulfilmentType.ACCOUNT_PROVISION,
        }
    ),
    ProductType.SOFTWARE_LICENSE: frozenset(
        {
            FulfilmentType.LICENSE_KEY,
            FulfilmentType.EMAIL,
            FulfilmentType.DOWNLOAD,
        }
    ),
    ProductType.PHYSICAL: frozenset(
        {
            FulfilmentType.SHIPMENT,
            FulfilmentType.LOCAL_DELIVERY,
            FulfilmentType.STORE_PICKUP,
            FulfilmentType.MANUAL,
        }
    ),
    ProductType.RENTAL: frozenset(
        {
            FulfilmentType.SHIPMENT,
            FulfilmentType.LOCAL_DELIVERY,
            FulfilmentType.STORE_PICKUP,
            FulfilmentType.MANUAL,
        }
    ),
    ProductType.MEMBERSHIP: frozenset(
        {
            FulfilmentType.SUBSCRIPTION,
            FulfilmentType.ACCOUNT_PROVISION,
            FulfilmentType.EMAIL,
            FulfilmentType.MANUAL,
        }
    ),
    ProductType.GIFT_CARD: frozenset(
        {
            FulfilmentType.EMAIL,
            FulfilmentType.DOWNLOAD,
            FulfilmentType.SHIPMENT,
            FulfilmentType.MANUAL,
        }
    ),
    ProductType.DONATION: frozenset(
        {
            FulfilmentType.EMAIL,
            FulfilmentType.MANUAL,
        }
    ),
    ProductType.PRE_ORDER: frozenset(
        {
            FulfilmentType.SHIPMENT,
            FulfilmentType.LOCAL_DELIVERY,
            FulfilmentType.STORE_PICKUP,
            FulfilmentType.DOWNLOAD,
            FulfilmentType.EMAIL,
            FulfilmentType.LICENSE_KEY,
            FulfilmentType.MANUAL,
        }
    ),
    # BUNDLE is intentionally left unmapped: a bundle's real fulfilment mix is
    # determined by the products/variants it contains, which can span physical
    # and digital delivery at once. `validate_type_fulfilment_combination`
    # treats a missing key as "no restriction" (see below), so any
    # FulfilmentType is accepted for a bundle rather than forcing a false
    # single-channel choice.
}


def validate_product_slug(value: str) -> None:
    if not _SLUG_RE.match(value):
        raise ValidationError(
            _(
                "'%(value)s' is not a valid slug. "
                "Use lowercase letters, digits, and hyphens only. "
                "Example: 'red-cotton-t-shirt'."
            )
            % {"value": value}
        )


def get_allowed_fulfilment_types(product_type: str) -> frozenset[str] | None:
    return _VALID_FULFILMENT.get(product_type)


def validate_type_fulfilment_combination(
    product_type: str,
    fulfilment_type: str,
) -> None:
    allowed = _VALID_FULFILMENT.get(product_type)
    if allowed is not None and fulfilment_type not in allowed:
        raise ValidationError(
            _(
                "Fulfilment type '%(ft)s' is not valid for product type '%(pt)s'. "
                "Allowed: %(allowed)s."
            )
            % {
                "ft": fulfilment_type,
                "pt": product_type,
                "allowed": ", ".join(sorted(allowed)),
            }
        )


_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_\.]{0,98}[A-Za-z0-9]$|^[A-Za-z0-9]$")


def validate_sku(value: str) -> None:
    if not value:
        raise ValidationError(_("SKU must not be empty."))
    if len(value) > SKU_MAX_LENGTH:
        raise ValidationError(
            _("SKU must be 100 characters or fewer (%(n)d given).") % {"n": len(value)}
        )
    if not _SKU_RE.match(value):
        raise ValidationError(
            _(
                "'%(value)s' is not a valid SKU. "
                "Use letters, digits, hyphens, underscores, or dots. "
                "Must start and end with a letter or digit."
            )
            % {"value": value}
        )


def validate_positive_dimension(value: object) -> None:
    if value is None:
        return
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValidationError(_("Value must be a number.")) from exc
    if numeric <= 0:
        raise ValidationError(
            _("Dimension must be greater than zero (got %(v)s).") % {"v": value}
        )


_ATTR_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_OPTION_VALUE_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_attribute_name(value: str) -> None:
    if not _ATTR_NAME_RE.match(value):
        raise ValidationError(
            _(
                "'%(value)s' is not a valid attribute name. "
                "Use lowercase letters, digits, and underscores only, "
                "starting with a letter. Example: 'storage_capacity'."
            )
            % {"value": value}
        )


def validate_option_value(value: str) -> None:
    if not _OPTION_VALUE_RE.match(value):
        raise ValidationError(
            _(
                "'%(value)s' is not a valid option value. "
                "Use letters, digits, underscores, or hyphens. "
                "No spaces allowed."
            )
            % {"value": value}
        )


def validate_hex_color(value: str) -> None:
    if not _HEX_COLOR_RE.match(value):
        raise ValidationError(
            _(
                "'%(value)s' is not a valid hex colour. "
                "Use the format #RRGGBB, e.g. '#FF5733'."
            )
            % {"value": value}
        )


# Unit symbol validation


# Build a flat set of all valid pint symbols from our curated catalogue
# (excluding the sentinel empty string used for "no unit").
_VALID_UNIT_SYMBOLS: frozenset[str] = frozenset(
    symbol
    for units in UNITS_BY_DIMENSION.values()
    for symbol, _label in units
    if symbol  # skip the empty-string sentinel in NONE dimension
)

# Also build a dimension -> frozenset map for cross-field validation
_SYMBOLS_BY_DIMENSION: dict[str, frozenset[str]] = {
    dim: frozenset(sym for sym, _lbl in units if sym)
    for dim, units in UNITS_BY_DIMENSION.items()
}


def validate_unit_symbol(value: str) -> None:
    if not value:
        return  # blank is allowed - unit is optional
    if value not in _VALID_UNIT_SYMBOLS:
        raise ValidationError(
            _(
                "'%(value)s' is not a recognised unit symbol. "
                "Choose a unit from the Unit Symbol dropdown."
            )
            % {"value": value}
        )


def validate_unit_symbol_matches_dimension(
    unit_dimension: str,
    unit_symbol: str,
) -> None:
    if not unit_symbol:
        return  # no symbol set - nothing to cross-check
    if unit_dimension == UnitDimension.NONE:
        # NONE dimension allows the empty string AND the NONE-group symbols
        allowed = _SYMBOLS_BY_DIMENSION.get(UnitDimension.NONE, frozenset())
        if unit_symbol and unit_symbol not in allowed:
            raise ValidationError(
                _("Unit symbol '%(sym)s' is not valid for the '%(dim)s' dimension.")
                % {
                    "sym": unit_symbol,
                    "dim": UnitDimension(unit_dimension).label,
                }
            )
        return

    allowed = _SYMBOLS_BY_DIMENSION.get(unit_dimension, frozenset())
    if unit_symbol not in allowed:
        raise ValidationError(
            _(
                "Unit symbol '%(sym)s' does not belong to the "
                "'%(dim)s' dimension. "
                "Choose a symbol that matches the selected dimension."
            )
            % {
                "sym": unit_symbol,
                "dim": UnitDimension(unit_dimension).label,
            }
        )
