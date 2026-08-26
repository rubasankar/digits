from __future__ import annotations

from django.test import TestCase

from core.enums import AddressChoices


class AddressChoicesValueTests(TestCase):
    def test_shipping_value(self) -> None:
        assert AddressChoices.SHIPPING.value == "SHIP"

    def test_billing_value(self) -> None:
        assert AddressChoices.BILLING.value == "BILL"

    def test_both_value(self) -> None:
        assert AddressChoices.BOTH.value == "BOTH"


class AddressChoicesLabelTests(TestCase):
    def test_shipping_label(self) -> None:
        assert AddressChoices.SHIPPING.label == "Shipping"

    def test_billing_label(self) -> None:
        assert AddressChoices.BILLING.label == "Billing"

    def test_both_label(self) -> None:
        assert AddressChoices.BOTH.label == "Both"


class AddressChoicesCompletenessTests(TestCase):
    def test_exactly_three_choices(self) -> None:
        assert len(AddressChoices) == 3

    def test_all_values_present(self) -> None:
        values = {c.value for c in AddressChoices}
        assert values == {"SHIP", "BILL", "BOTH"}

    def test_is_text_choices(self) -> None:
        from django.db.models import TextChoices

        assert issubclass(AddressChoices, TextChoices)
