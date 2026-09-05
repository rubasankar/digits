from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from django.apps import apps as django_apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test import override_settings

from apps.catalogue.models.category import ProductCategory
from apps.pricing.models import Currency
from core.sample_data import SAMPLE_DATA_SPECS
from core.sample_data import SeedSpec
from core.sample_data import _resolve_reference
from core.sample_data import apply_image_url
from core.sample_data import build_sample_data_index
from core.sample_data import clear_seed_spec
from core.sample_data import fetch_image_content
from core.sample_data import get_fixture_path
from core.sample_data import get_sample_data_root
from core.sample_data import get_seed_model
from core.sample_data import iter_sample_data_choices
from core.sample_data import load_fixture_json
from core.sample_data import load_seed_spec
from core.sample_data import normalize_model_key
from core.sample_data import resolve_payload
from core.sample_data import resolve_seed_specs
from core.sample_data import seed_entry
from core.sample_data import seed_regular_model
from core.sample_data import seed_tree_node
from core.sample_data import validate_seed_entry

# normalize_model_key


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


# SeedSpec dataclass


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


# SAMPLE_DATA_SPECS ordering


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


# iter_sample_data_choices


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


# build_sample_data_index


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


# resolve_seed_specs


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


# sample_data management command


def _currency_fixture(tmpdir: Path, entries: list[object]) -> None:
    fixture_dir = tmpdir / "pricing"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "currency.json").write_text(json.dumps(entries), encoding="utf-8")


class SampleDataCommandLoadTests(TestCase):
    def test_no_resolved_specs_raises_command_error(self) -> None:
        with (
            mock.patch(
                "core.management.commands.sample_data.resolve_seed_specs",
                return_value=[],
            ),
            pytest.raises(CommandError, match="No sample data models"),
        ):
            call_command("sample_data", "--model", "currency")

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


# helpers for the extended coverage


def _currency_spec() -> SeedSpec:
    return next(s for s in SAMPLE_DATA_SPECS if s.label == "currency")


def _make_currency(code: str = "USD", **overrides: object) -> Currency:
    defaults: dict[str, object] = {
        "symbol": "$",
        "name": "Dollar",
        "is_default": False,
        "is_active": True,
    }
    defaults.update(overrides)
    return Currency.objects.create(code=code, **defaults)


# get_sample_data_root / get_fixture_path


class SampleDataRootTests(TestCase):
    def test_default_root_points_inside_base_dir(self) -> None:
        expected = Path(settings.BASE_DIR) / "fixtures" / "sample_data"
        assert get_sample_data_root() == expected

    def test_configured_root_is_used(self) -> None:
        with override_settings(SAMPLE_DATA_DIR="/custom/data"):
            assert get_sample_data_root() == Path("/custom/data")

    def test_fixture_path_joins_spec_fixture_file(self) -> None:
        assert get_fixture_path(_currency_spec()) == (
            get_sample_data_root() / "pricing" / "currency.json"
        )


# get_seed_model


class GetSeedModelTests(TestCase):
    def test_resolves_an_installed_model(self) -> None:
        assert get_seed_model(_currency_spec()) is Currency

    def test_unresolvable_model_raises_command_error(self) -> None:
        spec = SeedSpec("bogus", "core", "NoSuchModelXYZ", "core/nope.json")
        with (
            mock.patch.object(django_apps, "get_model", return_value=None),
            pytest.raises(CommandError, match="Unable to resolve model"),
        ):
            get_seed_model(spec)


# load_fixture_json


class LoadFixtureJsonTests(TestCase):
    def test_returns_validated_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {"lookup": {"code": "USD"}, "fields": {"symbol": "$"}},
                    {"lookup": {"code": "INR"}, "fields": {"symbol": "R"}},
                ],
            )
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                data = load_fixture_json(_currency_spec())
        assert data == [
            {"lookup": {"code": "USD"}, "fields": {"symbol": "$"}},
            {"lookup": {"code": "INR"}, "fields": {"symbol": "R"}},
        ]

    def test_missing_file_raises_command_error(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(SAMPLE_DATA_DIR=str(tmpdir)),
            pytest.raises(CommandError, match="Missing sample data file"),
        ):
            load_fixture_json(_currency_spec())

    def test_non_list_json_raises_command_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fixture_dir = root / "pricing"
            fixture_dir.mkdir(parents=True, exist_ok=True)
            (fixture_dir / "currency.json").write_text("{}", encoding="utf-8")
            with (
                override_settings(SAMPLE_DATA_DIR=str(root)),
                pytest.raises(CommandError, match="must contain a JSON list"),
            ):
                load_fixture_json(_currency_spec())

    def test_non_dict_entry_raises_command_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(root, ["not-a-dict"])
            with (
                override_settings(SAMPLE_DATA_DIR=str(root)),
                pytest.raises(CommandError, match="must be an object"),
            ):
                load_fixture_json(_currency_spec())


# validate_seed_entry


class ValidateSeedEntryTests(TestCase):
    def test_valid_entry_returns_resolved_lookup_and_fields(self) -> None:
        entry = {"lookup": {"code": "USD"}, "fields": {"name": "Dollar"}}
        lookup, fields = validate_seed_entry(entry, _currency_spec())
        assert lookup == {"code": "USD"}
        assert fields == {"name": "Dollar"}

    def test_missing_lookup_raises_command_error(self) -> None:
        with pytest.raises(CommandError, match="lookup object"):
            validate_seed_entry({"fields": {}}, _currency_spec())

    def test_non_dict_fields_raises_command_error(self) -> None:
        with pytest.raises(CommandError, match="fields object"):
            validate_seed_entry(
                {"lookup": {"code": "USD"}, "fields": "bad"}, _currency_spec()
            )


# fetch_image_content


class FetchImageContentTests(TestCase):
    def test_downloads_bytes_from_url(self) -> None:
        with mock.patch("urllib.request.urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b"raw"
            result = fetch_image_content("https://example.com/pic.png")
        assert result == b"raw"

    def test_network_failure_raises_command_error(self) -> None:
        with (
            mock.patch(
                "urllib.request.urlopen", side_effect=OSError("connection down")
            ),
            pytest.raises(CommandError, match="Failed to download image"),
        ):
            fetch_image_content("https://example.com/pic.png")


# apply_image_url


class ApplyImageUrlTests(TestCase):
    def test_saves_bytes_under_filename_derived_from_url(self) -> None:
        obj = mock.MagicMock()
        with mock.patch("core.sample_data.fetch_image_content", return_value=b"img"):
            apply_image_url(obj, "image", "https://example.com/a/b/logo.png")
        obj.image.save.assert_called_once()
        args = obj.image.save.call_args[0]
        assert args[0] == "logo.png"
        assert args[1].read() == b"img"

    def test_strips_query_string_from_filename(self) -> None:
        obj = mock.MagicMock()
        with mock.patch("core.sample_data.fetch_image_content", return_value=b"img"):
            apply_image_url(
                obj, "image", "https://example.com/photo.JPG?size=thumb&v=2"
            )
        args = obj.image.save.call_args[0]
        assert args[0] == "photo.JPG"

    def test_falls_back_to_generic_filename_without_extension(self) -> None:
        obj = mock.MagicMock()
        with mock.patch("core.sample_data.fetch_image_content", return_value=b"img"):
            apply_image_url(obj, "image", "https://example.com/category/")
        args = obj.image.save.call_args[0]
        assert args[0] == "image_sample.jpg"


# seed_tree_node


class SeedTreeNodeTests(TestCase):
    def test_tree_node_model(self) -> None:
        from treebeard.mp_tree import MP_Node

        assert issubclass(ProductCategory, MP_Node)

    def test_creates_root_when_lookup_matches_nothing(self) -> None:
        from apps.pricing.models import TaxClass

        tax = TaxClass.objects.create(name="GST")
        seed_tree_node(
            ProductCategory,
            {"slug": "brand-new"},
            {
                "name": "Brand New",
                "description": "d",
                "is_active": True,
                "default_tax_class": tax,
            },
        )
        category = ProductCategory.objects.get(slug="brand-new")
        assert category.name == "Brand New"
        assert category.is_active is True
        assert category.default_tax_class_id == tax.pk

    def test_updates_existing_node_when_lookup_matches(self) -> None:
        ProductCategory.objects.add_root(
            create_kwargs={"name": "Old Name", "slug": "existing-cat"}
        )
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
            mock.patch(
                "core.sample_data.fetch_image_content", return_value=b"img-bytes"
            ),
        ):
            seed_tree_node(
                ProductCategory,
                {"slug": "existing-cat"},
                {
                    "name": "Updated Name",
                    "description": "updated",
                    "is_active": False,
                    "image_url": "https://example.com/existing.png",
                },
            )
        category = ProductCategory.objects.get(slug="existing-cat")
        assert category.name == "Updated Name"
        assert category.description == "updated"
        assert category.is_active is False
        assert category.image.name.endswith("existing.png")

    def test_new_node_with_image_url_applies_image(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            override_settings(MEDIA_ROOT=tmpdir),
            mock.patch(
                "core.sample_data.fetch_image_content", return_value=b"img-bytes"
            ),
        ):
            seed_tree_node(
                ProductCategory,
                {"slug": "cat-with-image"},
                {
                    "name": "Cat With Image",
                    "description": "",
                    "is_active": True,
                    "image_url": "https://example.com/cat.png",
                },
            )
        category = ProductCategory.objects.get(slug="cat-with-image")
        assert category.image.name.endswith("cat.png")


# seed_regular_model


class SeedRegularModelTests(TestCase):
    def test_creates_or_updates_via_lookup(self) -> None:
        model = mock.MagicMock()
        obj = mock.MagicMock()
        model.objects.update_or_create.return_value = (obj, True)
        seed_regular_model(
            model,
            {"code": "ABC"},
            {"name": "Seeded", "symbol": "$"},
        )
        model.objects.update_or_create.assert_called_once_with(
            code="ABC",
            defaults={"name": "Seeded", "symbol": "$"},
        )

    def test_with_image_url_saves_image_field_and_updates(self) -> None:
        model = mock.MagicMock()
        obj = mock.MagicMock()
        model.objects.update_or_create.return_value = (obj, True)
        with mock.patch("core.sample_data.fetch_image_content", return_value=b"img"):
            seed_regular_model(
                model,
                {"code": "ABC"},
                {"name": "Seeded", "image_url": "https://example.com/logo.png"},
            )
        model.objects.update_or_create.assert_called_once()
        obj.image.save.assert_called_once()
        obj.save.assert_called_once_with(update_fields=["image"])


# seed_entry


class SeedEntryTests(TestCase):
    def test_seeds_a_regular_model(self) -> None:
        seed_entry(
            _currency_spec(),
            {
                "lookup": {"code": "USD"},
                "fields": {
                    "symbol": "$",
                    "name": "US Dollar",
                    "is_default": False,
                    "is_active": True,
                },
            },
        )
        currency = Currency.objects.get(code="USD")
        assert currency.name == "US Dollar"
        assert currency.symbol == "$"

    def test_seeds_a_tree_model(self) -> None:
        spec = next(s for s in SAMPLE_DATA_SPECS if s.label == "product category")
        seed_entry(
            spec,
            {
                "lookup": {"slug": "seeded-category"},
                "fields": {
                    "name": "Seeded Category",
                    "description": "",
                    "is_active": True,
                },
            },
        )
        assert ProductCategory.objects.filter(slug="seeded-category").exists()


# resolve_payload / _resolve_reference


class ResolvePayloadTests(TestCase):
    def test_primitives_are_returned_unchanged(self) -> None:
        assert resolve_payload("text") == "text"
        assert resolve_payload(42) == 42
        assert resolve_payload(None) is None
        truthy = True
        assert resolve_payload(truthy) is True

    def test_list_is_recursively_resolved(self) -> None:
        assert resolve_payload([1, "a", [2, {"x": "y"}]]) == [1, "a", [2, {"x": "y"}]]

    def test_dict_without_ref_is_recursively_resolved(self) -> None:
        assert resolve_payload({"a": {"b": [1, 2]}}) == {"a": {"b": [1, 2]}}

    def test_dict_with_ref_resolves_to_model_instance(self) -> None:
        currency = _make_currency(code="INR", name="Indian Rupee", symbol="INR")
        result = resolve_payload(
            {"$ref": "pricing.Currency", "lookup": {"code": "INR"}}
        )
        assert result == currency


class ResolveReferenceTests(TestCase):
    def test_non_ref_dict_recurses_payload(self) -> None:
        assert _resolve_reference({"a": {"b": [1]}}) == {"a": {"b": [1]}}

    def test_known_model_reference_returns_instance(self) -> None:
        currency = _make_currency(code="JPY", name="Yen", symbol="Y")
        result = _resolve_reference(
            {"$ref": "pricing.Currency", "lookup": {"code": "JPY"}}
        )
        assert result == currency

    def test_unknown_model_reference_raises_command_error(self) -> None:
        with pytest.raises(CommandError, match="Unknown model reference"):
            _resolve_reference({"$ref": "nope.Nope", "lookup": {"code": "X"}})

    def test_non_dict_lookup_raises_command_error(self) -> None:
        with pytest.raises(CommandError, match="Reference lookups"):
            _resolve_reference({"$ref": "pricing.Currency", "lookup": "bad"})


# load_seed_spec / clear_seed_spec


class LoadSeedSpecTests(TestCase):
    def test_returns_number_of_loaded_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {
                        "lookup": {"code": "USD"},
                        "fields": {
                            "symbol": "$",
                            "name": "Dollar",
                            "is_default": False,
                            "is_active": True,
                        },
                    },
                    {
                        "lookup": {"code": "EUR"},
                        "fields": {
                            "symbol": "E",
                            "name": "Euro",
                            "is_default": False,
                            "is_active": True,
                        },
                    },
                ],
            )
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                count = load_seed_spec(_currency_spec())
        assert count == 2
        assert Currency.objects.filter(code__in=["USD", "EUR"]).count() == 2

    def test_fresh_flag_clears_existing_rows_first(self) -> None:
        _make_currency(code="GBP", name="Pound", symbol="P")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _currency_fixture(
                root,
                [
                    {
                        "lookup": {"code": "CAD"},
                        "fields": {
                            "symbol": "C",
                            "name": "Canadian Dollar",
                            "is_default": False,
                            "is_active": True,
                        },
                    }
                ],
            )
            with override_settings(SAMPLE_DATA_DIR=str(root)):
                load_seed_spec(_currency_spec(), fresh=True)
        assert Currency.objects.filter(code="GBP").count() == 0
        assert Currency.objects.filter(code="CAD").count() == 1


class ClearSeedSpecTests(TestCase):
    def test_deletes_all_rows_for_spec_model(self) -> None:
        _make_currency(code="USD")
        _make_currency(code="INR", name="Rupee", symbol="R")
        deleted = clear_seed_spec(_currency_spec())
        assert deleted >= 2
        assert Currency.objects.count() == 0

    def test_returns_zero_when_no_rows(self) -> None:
        assert clear_seed_spec(_currency_spec()) == 0
