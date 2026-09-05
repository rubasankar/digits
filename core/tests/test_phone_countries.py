from __future__ import annotations

from unittest import mock

import phonenumbers
from django.test import SimpleTestCase

from core.phone_countries import CountryEntry
from core.phone_countries import get_phone_countries


class GetPhoneCountriesTests(SimpleTestCase):
    def test_returns_list_of_country_entries(self) -> None:
        countries = get_phone_countries(default_region="US")
        assert len(countries) > 0
        for entry in countries:
            assert isinstance(entry, dict)
            assert set(entry.keys()) == {"code", "dial_code", "name"}

    def test_dial_codes_are_prefixed_with_plus(self) -> None:
        countries = get_phone_countries(default_region="US")
        for entry in countries:
            assert entry["dial_code"].startswith("+")

    def test_entries_are_sorted_by_name(self) -> None:
        countries = get_phone_countries(default_region="US")
        names = [entry["name"] for entry in countries]
        assert names[0] == "United States"
        assert names[1:] == sorted(names[1:])

    def test_default_region_is_moved_to_front(self) -> None:
        countries = get_phone_countries(default_region="IN")
        assert countries[0]["code"] == "IN"
        assert countries[0]["name"] == "India"

    def test_different_default_region_order(self) -> None:
        countries = get_phone_countries(default_region="GB")
        assert countries[0]["code"] == "GB"

    def test_skips_regions_without_a_country_code(self) -> None:
        get_phone_countries.cache_clear()
        try:
            with mock.patch.object(
                phonenumbers, "country_code_for_region", return_value=0
            ):
                countries = get_phone_countries(default_region="US")
        finally:
            get_phone_countries.cache_clear()
        assert countries == []

    def test_unknown_default_region_keeps_sorted_order(self) -> None:
        countries = get_phone_countries(default_region="XX")
        assert countries[0]["code"] != "XX"


class CountryEntryTypingTests(SimpleTestCase):
    def test_required_keys_present(self) -> None:
        import typing

        assert typing.get_type_hints(CountryEntry) == {
            "code": str,
            "dial_code": str,
            "name": str,
        }
