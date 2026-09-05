from __future__ import annotations

from django.template import Context
from django.template import Template
from django.test import SimpleTestCase
from django.test import override_settings


class DefaultPhoneRegionTagTests(SimpleTestCase):
    @override_settings(PHONENUMBER_DEFAULT_REGION="IN")
    def test_returns_configured_region(self) -> None:
        from core.templatetags.phone_tags import default_phone_region

        assert default_phone_region() == "IN"

    @override_settings(PHONENUMBER_DEFAULT_REGION="US")
    def test_returns_region_as_string(self) -> None:
        from core.templatetags.phone_tags import default_phone_region

        assert isinstance(default_phone_region(), str)
        assert default_phone_region() == "US"

    @override_settings(PHONENUMBER_DEFAULT_REGION="GB")
    def test_tag_renders_inside_template(self) -> None:
        template = Template("{% load phone_tags %}{% default_phone_region %}")
        assert template.render(Context({})) == "GB"


class PhoneCountriesTagTests(SimpleTestCase):
    @override_settings(PHONENUMBER_DEFAULT_REGION="IN")
    def test_returns_country_list_with_default_first(self) -> None:
        from core.templatetags.phone_tags import phone_countries

        countries = phone_countries()
        assert len(countries) > 0
        assert countries[0]["code"] == "IN"

    @override_settings(PHONENUMBER_DEFAULT_REGION="US")
    def test_default_region_taken_from_settings(self) -> None:
        from core.templatetags.phone_tags import phone_countries

        countries = phone_countries()
        assert countries[0]["code"] == "US"

    @override_settings(PHONENUMBER_DEFAULT_REGION="IN")
    def test_tag_renders_countries_in_template(self) -> None:
        template = Template(
            "{% load phone_tags %}{% phone_countries as countries %}"
            "{{ countries|length }}"
        )
        rendered = template.render(Context({}))
        assert int(rendered) > 0
