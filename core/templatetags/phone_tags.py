"""Template tags for phone number country list and default region."""

from __future__ import annotations

from django import template
from django.conf import settings

from core.phone_countries import CountryEntry
from core.phone_countries import get_phone_countries

register = template.Library()


@register.simple_tag
def phone_countries() -> list[CountryEntry]:
    """Return the full country/dial-code list, default region first."""
    region: str = getattr(settings, "PHONENUMBER_DEFAULT_REGION", "US")
    return get_phone_countries(region)


@register.simple_tag
def default_phone_region() -> str:
    """Return the configured default phone region code (e.g. 'IN')."""
    return str(getattr(settings, "PHONENUMBER_DEFAULT_REGION", "US"))
