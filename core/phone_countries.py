"""Builds a sorted country/dial-code list from the phonenumbers library."""

from __future__ import annotations

import functools
from typing import TypedDict

import phonenumbers
from babel import Locale


class CountryEntry(TypedDict):
    """Single entry in the phone country list."""

    code: str
    dial_code: str
    name: str


@functools.cache
def get_phone_countries(default_region: str = "US") -> list[CountryEntry]:
    """Return a sorted list of countries with dial codes, default region first."""
    locale = Locale("en")
    entries: list[CountryEntry] = []

    for region in phonenumbers.SUPPORTED_REGIONS:
        numeric = phonenumbers.country_code_for_region(region)
        if numeric == 0:
            continue
        name: str = locale.territories.get(region) or region
        entries.append(
            CountryEntry(
                code=region,
                dial_code=f"+{numeric}",
                name=name,
            )
        )

    entries.sort(key=lambda e: e["name"])

    default_upper = default_region.upper()
    idx = next(
        (i for i, e in enumerate(entries) if e["code"] == default_upper),
        None,
    )
    if idx is not None and idx != 0:
        entries.insert(0, entries.pop(idx))

    return entries
