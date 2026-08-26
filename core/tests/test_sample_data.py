from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test import override_settings

from apps.pricing.models import Currency
from core.sample_data import SAMPLE_DATA_SPECS
from core.sample_data import SeedSpec
from core.sample_data import build_sample_data_index
from core.sample_data import iter_sample_data_choices
from core.sample_data import normalize_model_key
from core.sample_data import resolve_seed_specs

# ---------------------------------------------------------------------------
# normalize_model_key
# ---------------------------------------------------------------------------


class NormalizeModelKeyTests(TestCase):
    def test_lowercases_input(self) -> None:
        assert normalize_model_key("Currency") == "currency"

    def test_dots_become_dashes(self) -> None:
        assert normalize_model_key("pricing.Currency") == "pricing-currency"

    def test_underscores_become_dashes(self) -> None:
        assert normalize_model_key("tax_class") == "tax-class"

    def test_leading_and_trailing_spaces_stripped(self) -> None:
        assert normalize_model_key("  product  ") == "product"

    def test_multi_word_with_spaces(self) -> None:
        assert normalize_model_key("product variant") == "product-variant"

    def test_already_normalised_unchanged(self) -> None:
        assert normalize_model_key("currency") == "currency"


# ---------------------------------------------------------------------------
# SeedSpec dataclass
# ---------------------------------------------------------------------------


class SeedSpecTests(TestCase):
    def test_django_label_property(self) -> None:
        spec = SeedSpec(
            label="currency",
            app_label="pricing",
            model_name="Currency",
            fixture_file="pricing/currency.json",
        )
        assert spec.django_label == "pricing.Currency"

    def test_frozen_cannot_be_mutated(self) -> None:
        spec = SeedSpec(
            label="currency",
            app_label="pricing",
            model_name="Currency",
            fixture_file="pricing/currency.json",
        )
        with pytest.raises((AttributeError, TypeError)):
            spec.label = "other"  # type: ignore[misc]

    def test_aliases_default_to_empty_tuple(self) -> None:
        spec = SeedSpec(
            label="currency",
            app_label="pricing",
            model_name="Currency",
            fixture_file="pricing/currency.json",
        )
        assert spec.aliases == ()


# ---------------------------------------------------------------------------
# SAMPLE_DATA_SPECS ordering
# ---------------------------------------------------------------------------


class SampleDataSpecsTests(TestCase):
    def test_currency_before_tax_class(self) -> None:
        labels = [s.label for s in SAMPLE_DATA_SPECS]
        assert labels.index("currency") < labels.index("tax class")

    def test_product_before_product_variant(self) -> None:
        labels = [s.label for s in SAMPLE_DATA_SPECS]
        assert labels.index("product") < labels.index("product variant")

    def test_user_account_before_staff_profile(self) -> None:
        labels = [s.label for s in SAMPLE_DATA_SPECS]
        assert labels.index("user account") < labels.index("staff profile")

    def test_product_category_before_product(self) -> None:
        labels = [s.label for s in SAMPLE_DATA_SPECS]
        assert labels.index("product category") < labels.index("product")


# ---------------------------------------------------------------------------
# iter_sample_data_choices
# ---------------------------------------------------------------------------


class IterSampleDataChoicesTests(TestCase):
    def test_returns_sorted_list(self) -> None:
        choices = iter_sample_data_choices()
        assert choices == sorted(choices)

    def test_includes_primary_labels(self) -> None:
        choices = iter_sample_data_choices()
        for label in ("currency", "product", "tax class", "warehouse"):
            assert label in choices, f"'{label}' missing from choices"

    def test_includes_aliases(self) -> None:
        choices = iter_sample_data_choices()
        assert "currencies" in choices
        assert "products" in choices
        assert "variants" in choices

    def test_no_duplicates(self) -> None:
        choices = iter_sample_data_choices()
        assert len(choices) == len(set(choices))


# ---------------------------------------------------------------------------
# build_sample_data_index
# ---------------------------------------------------------------------------


class BuildSampleDataIndexTests(TestCase):
    def test_primary_label_resolves(self) -> None:
        index = build_sample_data_index()
        assert "currency" in index
        assert index["currency"].app_label == "pricing"

    def test_django_label_resolves(self) -> None:
        index = build_sample_data_index()
        assert "pricing-currency" in index

    def test_alias_resolves_to_correct_spec(self) -> None:
        index = build_sample_data_index()
        assert "currencies" in index
        assert index["currencies"].label == "currency"

    def test_all_specs_reachable_via_label(self) -> None:
        index = build_sample_data_index()
        for spec in SAMPLE_DATA_SPECS:
            key = normalize_model_key(spec.label)
            assert key in index, f"Label '{spec.label}' not in index"


# ---------------------------------------------------------------------------
# resolve_seed_specs
# ---------------------------------------------------------------------------


class ResolveSeedSpecsTests(TestCase):
    def test_empty_list_returns_all_specs(self) -> None:
        specs = resolve_seed_specs([])
        assert len(specs) == len(SAMPLE_DATA_SPECS)

    def test_none_returns_all_specs(self) -> None:
        specs = resolve_seed_specs(None)
        assert len(specs) == len(SAMPLE_DATA_SPECS)

    def test_single_label_returns_one_spec(self) -> None:
        specs = resolve_seed_specs(["currency"])
        assert len(specs) == 1
        assert specs[0].label == "currency"

    def test_alias_resolves_to_same_spec_as_label(self) -> None:
        by_label = resolve_seed_specs(["currency"])
        by_alias = resolve_seed_specs(["currencies"])
        assert by_label[0].django_label == by_alias[0].django_label

    def test_multiple_selections_maintain_registry_order(self) -> None:
        specs = resolve_seed_specs(["product", "product variant"])
        assert [s.label for s in specs] == ["product", "product variant"]

    def test_unknown_model_raises_command_error(self) -> None:
        with pytest.raises(CommandError) as ctx:
            resolve_seed_specs(["does-not-exist-xyz"])
        assert "does-not-exist-xyz" in str(ctx.value)

    def test_comma_separated_resolves_both(self) -> None:
        specs = resolve_seed_specs(["currency,tax class"])
        labels = [s.label for s in specs]
        assert "currency" in labels
        assert "tax class" in labels

    def test_deduplication_same_spec_twice(self) -> None:
        specs = resolve_seed_specs(["currency", "currencies"])
        assert len(specs) == 1


# ---------------------------------------------------------------------------
# sample_data management command
# ---------------------------------------------------------------------------


def _currency_fixture(tmpdir: Path, entries: list[dict[object, object]]) -> None:
    fixture_dir = tmpdir / "pricing"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "currency.json").write_text(json.dumps(entries), encoding="utf-8")


class SampleDataCommandLoadTests(TestCase):
    def test_fresh_flag_replaces_existing_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {
                        "lookup": {"code": "USD"},
                        "fields": {
                            "symbol": "$",
                            "name": "US Dollar",
                            "is_default": True,
                            "is_active": True,
                        },
                    }
                ],
            )
            Currency.objects.create(
                code="USD",
                symbol="OLD",
                name="Old Dollar",
                is_default=False,
                is_active=False,
            )
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                call_command("sample_data", "--model", "currency", "--fresh")

            assert Currency.objects.count() == 1
            c = Currency.objects.get(code="USD")
            assert c.symbol == "$"
            assert c.name == "US Dollar"
            assert c.is_default
            assert c.is_active

    def test_load_without_fresh_upserts_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {
                        "lookup": {"code": "EUR"},
                        "fields": {
                            "symbol": "E",
                            "name": "Euro",
                            "is_default": False,
                            "is_active": True,
                        },
                    }
                ],
            )
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                call_command("sample_data", "--model", "currency")
                call_command("sample_data", "--model", "currency")

            assert Currency.objects.filter(code="EUR").count() == 1

    def test_unknown_model_raises_command_error(self) -> None:
        with pytest.raises(CommandError):
            call_command("sample_data", "--model", "nonexistent-xyz")

    def test_success_output_message(self) -> None:
        from io import StringIO

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {
                        "lookup": {"code": "GBP"},
                        "fields": {
                            "symbol": "P",
                            "name": "Pound",
                            "is_default": False,
                            "is_active": True,
                        },
                    }
                ],
            )
            stdout = StringIO()
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                call_command("sample_data", "--model", "currency", stdout=stdout)
            output = stdout.getvalue()
            assert "complete" in output.lower() or "currency" in output.lower()
