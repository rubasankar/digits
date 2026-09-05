from __future__ import annotations

from django.test import TestCase

from apps.inventory.models import Warehouse
from apps.pricing.models import TaxClass
from core.models import AddressBaseModel
from core.models import BaseModel


class BaseModelSlugTests(TestCase):
    """Test the reusable BaseModel (auto-slug, __str__) via concrete subclasses."""

    def test_base_model_is_abstract(self) -> None:
        assert BaseModel._meta.abstract

    def test_slug_auto_generated_from_name_on_save(self) -> None:
        tax = TaxClass.objects.create(name="Standard Tax")
        tax.refresh_from_db()
        assert tax.slug == "standard-tax"

    def test_provided_slug_is_preserved(self) -> None:
        tax = TaxClass.objects.create(name="Standard Tax", slug="custom-slug")
        assert tax.slug == "custom-slug"

    def test_blank_slug_is_regenerated_on_update(self) -> None:
        tax = TaxClass.objects.create(name="First Name")
        tax.slug = ""
        tax.save()
        tax.refresh_from_db()
        assert tax.slug == "first-name"

    def test_duplicate_name_gets_suffixed_slug(self) -> None:
        TaxClass.objects.create(name="Collision")
        second = TaxClass.objects.create(name="Collision")
        assert second.slug == "collision-2"

    def test_names_differing_only_by_case_share_slug(self) -> None:
        TaxClass.objects.create(name="Mixed Case")
        second = TaxClass.objects.create(name="mixed case")
        assert second.slug == "mixed-case-2"

    def test_str_returns_name(self) -> None:
        tax = TaxClass.objects.create(name="VAT")
        assert str(tax) == "VAT"


class AddressBaseModelTests(TestCase):
    """Test the reusable AddressBaseModel via the concrete Warehouse subclass."""

    def test_address_base_model_is_abstract(self) -> None:
        assert AddressBaseModel._meta.abstract

    def _make_warehouse(self, **overrides: object) -> Warehouse:
        defaults: dict[str, object] = {
            "name": "Warehouse One",
            "code": "W-1",
            "address_line1": "1 Test Street",
            "city": "London",
            "state": "Greater London",
            "country": "GB",
            "pincode": "SW1 1AA",
        }
        defaults.update(overrides)
        return Warehouse.objects.create(**defaults)

    def test_optional_address_fields_default_to_blank(self) -> None:
        wh = self._make_warehouse()
        assert wh.address_line2 == ""
        assert wh.landmark == ""

    def test_address_values_are_persisted(self) -> None:
        wh = self._make_warehouse(
            address_line2="Flat 2",
            landmark="Near the station",
        )
        assert wh.address_line2 == "Flat 2"
        assert wh.landmark == "Near the station"
        assert wh.country == "GB"
        assert wh.pincode == "SW1 1AA"

    def test_inherits_uuid_pk_and_timestamps(self) -> None:
        wh = self._make_warehouse()
        assert wh.pk is not None
        assert len(str(wh.pk)) == 36
        assert wh.created is not None
        assert wh.modified is not None

    def test_id_field_is_uuid(self) -> None:
        from django.db.models import UUIDField

        field = Warehouse._meta.get_field("id")
        assert isinstance(field, UUIDField)
