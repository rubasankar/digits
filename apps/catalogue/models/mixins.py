from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import date
from datetime import datetime
from datetime import time
from decimal import Decimal
from decimal import InvalidOperation
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.validators import validate_email
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.catalogue.constants import ATTRIBUTE_VALUE_MAX_LENGTH
from apps.catalogue.constants import LONG_TEXT_MAX_LENGTH
from apps.catalogue.constants import MULTI_SELECT_MAX_OPTIONS
from apps.catalogue.constants import MULTI_SELECT_SEPARATOR
from apps.catalogue.enums import AttributeValueType

if TYPE_CHECKING:
    from apps.catalogue.models.attribute import AttributeDefinition

_URL_VALIDATOR = URLValidator()
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

type JSONValue = dict[str, Any] | list[Any]
type TypedValue = (
    str
    | int
    | float
    | Decimal
    | bool
    | date
    | time
    | datetime
    | JSONValue
    | uuid.UUID
    | None
)
type CoerceFn = Callable[[str], TypedValue]
type ValidateFn = Callable[[str], None]


# Coercion helpers -- one small function per type group


def _coerce_int(v: str) -> int | None:
    try:
        return int(v)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _coerce_decimal(v: str) -> Decimal | None:
    try:
        return Decimal(v)
    except (InvalidOperation, TypeError):  # fmt: skip
        return None


def _coerce_float(v: str) -> float | None:
    try:
        return float(v)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _coerce_date(v: str) -> date | None:
    try:
        return date.fromisoformat(v)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _coerce_time(v: str) -> time | None:
    try:
        return time.fromisoformat(v)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _coerce_datetime(v: str) -> datetime | None:
    try:
        return datetime.fromisoformat(v)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _coerce_json(v: str) -> JSONValue | None:
    try:
        return cast("JSONValue", json.loads(v))
    except (json.JSONDecodeError, TypeError):  # fmt: skip
        return None


def _coerce_uuid(v: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(v)
    except (ValueError, AttributeError):  # fmt: skip
        return None


# Validation helpers -- raise ValidationError or return None


def _validate_int(v: str) -> None:
    try:
        int(v)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid integer.") % {"v": v}}
        ) from exc


def _validate_decimal(v: str) -> None:
    try:
        Decimal(v)
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid decimal.") % {"v": v}}
        ) from exc


def _validate_float(v: str) -> None:
    try:
        float(v)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid float.") % {"v": v}}
        ) from exc


def _validate_boolean(v: str) -> None:
    if v.strip().lower() not in ("true", "false"):
        raise ValidationError({"value": _("Boolean value must be 'true' or 'false'.")})


def _validate_date(v: str) -> None:
    try:
        date.fromisoformat(v)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid date (YYYY-MM-DD).") % {"v": v}}
        ) from exc


def _validate_time(v: str) -> None:
    try:
        time.fromisoformat(v)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid time (HH:MM:SS).") % {"v": v}}
        ) from exc


def _validate_datetime(v: str) -> None:
    try:
        datetime.fromisoformat(v)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid datetime (ISO 8601).") % {"v": v}}
        ) from exc


def _validate_json(v: str) -> None:
    try:
        json.loads(v)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not valid JSON.") % {"v": v}}
        ) from exc


def _validate_uuid(v: str) -> None:
    try:
        uuid.UUID(v)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid UUID.") % {"v": v}}
        ) from exc


def _validate_email(v: str) -> None:
    try:
        validate_email(v)
    except ValidationError as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid email address.") % {"v": v}}
        ) from exc


def _validate_url(v: str) -> None:
    try:
        _URL_VALIDATOR(v)
    except ValidationError as exc:
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid URL.") % {"v": v}}
        ) from exc


def _validate_color(v: str) -> None:
    if not _HEX_COLOR_RE.match(v):
        raise ValidationError(
            {"value": _("'%(v)s' is not a valid hex colour (#RRGGBB).") % {"v": v}}
        )


def _validate_long_text(v: str) -> None:
    if len(v) > LONG_TEXT_MAX_LENGTH:
        raise ValidationError(
            {
                "value": _("Value exceeds the maximum length of %(max)d characters.")
                % {"max": LONG_TEXT_MAX_LENGTH}
            }
        )


# Dispatch tables

VT = AttributeValueType

_COERCE: dict[str, CoerceFn] = {
    VT.INTEGER: _coerce_int,
    VT.BIG_INTEGER: _coerce_int,
    VT.DECIMAL: _coerce_decimal,
    VT.FLOAT: _coerce_float,
    VT.DATE: _coerce_date,
    VT.TIME: _coerce_time,
    VT.DATETIME: _coerce_datetime,
    VT.JSON: _coerce_json,
    VT.UUID: _coerce_uuid,
}

_VALIDATE: dict[str, ValidateFn] = {
    VT.INTEGER: _validate_int,
    VT.BIG_INTEGER: _validate_int,
    VT.DECIMAL: _validate_decimal,
    VT.FLOAT: _validate_float,
    VT.BOOLEAN: _validate_boolean,
    VT.DATE: _validate_date,
    VT.TIME: _validate_time,
    VT.DATETIME: _validate_datetime,
    VT.JSON: _validate_json,
    VT.UUID: _validate_uuid,
    VT.EMAIL: _validate_email,
    VT.URL: _validate_url,
    VT.COLOR: _validate_color,
    VT.LONG_TEXT: _validate_long_text,
}


# Mixins
class AttributeAssignmentMixin(models.Model):
    # Configuration flags
    is_required = models.BooleanField(
        _("Required"),
        default=False,
        help_text=_("A value must be supplied for every target entity."),
    )
    is_searchable = models.BooleanField(
        _("Searchable"),
        default=False,
        help_text=_("Include this attribute in full-text search indexing."),
    )
    is_filterable = models.BooleanField(
        _("Filterable"),
        default=False,
        help_text=_("Expose this attribute as a faceted filter in listings."),
    )
    is_comparable = models.BooleanField(
        _("Comparable"),
        default=False,
        help_text=_("Show this attribute in the product comparison table."),
    )
    visible_on_listing = models.BooleanField(
        _("Visible on Listing"),
        default=False,
        help_text=_("Show this attribute value on product listing cards."),
    )
    visible_on_detail = models.BooleanField(
        _("Visible on Detail"),
        default=True,
        help_text=_("Show this attribute value on the product detail page."),
    )
    allow_override = models.BooleanField(
        _("Allow Override"),
        default=True,
        help_text=_(
            "When True, a product or variant can override the category default value."
        ),
    )
    generates_variants = models.BooleanField(
        _("Generates Variants"),
        default=False,
        help_text=_(
            "When True (and scope=VARIANT), the variant service uses this "
            "attribute's options to build the SKU matrix."
        ),
    )
    default_value = models.CharField(
        _("Default Value"),
        max_length=ATTRIBUTE_VALUE_MAX_LENGTH,
        blank=True,
        help_text=_(
            "Pre-filled value for new entities assigned to this target. "
            "Leave blank for no default."
        ),
    )
    display_order = models.PositiveSmallIntegerField(
        _("Display Order"),
        default=0,
        help_text=_("Controls attribute ordering within a target. Lower = first."),
    )

    class Meta:
        abstract = True


class AttributeValueMixin(models.Model):
    definition: AttributeDefinition
    definition_id: object | None
    value = models.CharField(
        _("Value"),
        max_length=ATTRIBUTE_VALUE_MAX_LENGTH,
        blank=True,
        help_text=_(
            "All types stored as strings. "
            "Integer/BigInteger: '256'. Decimal/Float: '0.350'. "
            "Boolean: 'true'/'false'. Date: 'YYYY-MM-DD'. "
            "Time: 'HH:MM:SS'. DateTime: 'YYYY-MM-DDTHH:MM:SS'. "
            "JSON: valid JSON. UUID: standard UUID string. "
            "Colour: '#RRGGBB'. SingleSelect: one option value. "
            "MultiSelect: option values joined by ','."
        ),
    )

    class Meta:
        abstract = True

    @property
    def typed_value(self) -> TypedValue:
        vt: str = self.definition.value_type
        v: str = self.value

        coerce = _COERCE.get(vt)
        if coerce is not None:
            return coerce(v)

        if vt == VT.BOOLEAN:
            return v.strip().lower() == "true"

        if vt == VT.MULTI_SELECT:
            return [s.strip() for s in v.split(MULTI_SELECT_SEPARATOR) if s.strip()]
        return v

    def _validate_value(self) -> None:
        if not self.definition_id:
            return

        defn = self.definition
        vt: str = defn.value_type
        v: str = self.value

        if not v:
            # Blank means "not yet set" (e.g. an assignment with no default_value
            # provisioned at category/product/variant creation) - only type-specific
            # format checks are skipped, not presence, which is enforced elsewhere.
            return

        validate = _VALIDATE.get(vt)
        if validate is not None:
            validate(v)
            return

        if vt == VT.SINGLE_SELECT:
            self._validate_single_select(v, defn)
        elif vt == VT.MULTI_SELECT:
            self._validate_multi_select(v, defn)

    def _validate_single_select(self, v: str, defn: AttributeDefinition) -> None:
        allowed: list[str] = [opt.value for opt in defn.options.filter(is_active=True)]
        if allowed and v not in allowed:
            raise ValidationError(
                {
                    "value": _(
                        "'%(v)s' is not an allowed option. Choose from: %(opts)s."
                    )
                    % {"v": v, "opts": ", ".join(allowed)}
                }
            )

    def _validate_multi_select(self, v: str, defn: AttributeDefinition) -> None:
        tokens = [s.strip() for s in v.split(MULTI_SELECT_SEPARATOR) if s.strip()]

        if len(tokens) > MULTI_SELECT_MAX_OPTIONS:
            raise ValidationError(
                {
                    "value": _(
                        "Multi-select allows at most %(max)d options; %(n)d given."
                    )
                    % {"max": MULTI_SELECT_MAX_OPTIONS, "n": len(tokens)}
                }
            )

        allowed: list[str] = [opt.value for opt in defn.options.filter(is_active=True)]
        if allowed:
            invalid = [t for t in tokens if t not in allowed]
            if invalid:
                raise ValidationError(
                    {
                        "value": _("Invalid option(s): %(bad)s. Allowed: %(opts)s.")
                        % {"bad": ", ".join(invalid), "opts": ", ".join(allowed)}
                    }
                )


class MerchandisingMixin(models.Model):
    """Adds an is_featured flag for storefront promotion sections."""

    is_featured = models.BooleanField(
        _("Featured"),
        default=False,
        db_index=True,
        help_text=_(
            "Show this item in featured/promotional sections on the storefront."
        ),
    )

    class Meta:
        abstract = True
