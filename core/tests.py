from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings

from apps.catalogue.models.category import ProductCategory
from apps.catalogue.models.product import Product
from apps.customers.models import CustomerProfile
from apps.pricing.models import Currency
from apps.pricing.models import TaxClass
from apps.reviews.services import ReviewDraft
from apps.reviews.services import ReviewService
from core.sample_data import resolve_seed_specs

User = get_user_model()


class SampleDataCommandTests(TestCase):
    def test_registry_includes_product_and_variant(self) -> None:
        specs = resolve_seed_specs(["product", "product variant"])
        assert [spec.label for spec in specs] == ["product", "product variant"]

    def test_fresh_reload_only_selected_model_from_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_root = Path(tmpdir)
            fixture_dir = sample_root / "pricing"
            fixture_dir.mkdir(parents=True, exist_ok=True)
            (fixture_dir / "currency.json").write_text(
                json.dumps(
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
                    ]
                ),
                encoding="utf-8",
            )

            Currency.objects.create(
                code="USD",
                symbol="OLD",
                name="Old Dollar",
                is_default=False,
                is_active=False,
            )

            with override_settings(SAMPLE_DATA_DIR=str(sample_root)):
                call_command("sample_data", "--model", "currency", "--fresh")

            assert Currency.objects.count() == 1
            currency = Currency.objects.get(code="USD")
            assert currency.symbol == "$"
            assert currency.name == "US Dollar"
            assert currency.is_default
            assert currency.is_active


class ReviewAutoPublishFlagTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="customer@example.com")
        self.customer = CustomerProfile.objects.create(
            user=self.user,
            first_name="Casey",
            last_name="Customer",
        )
        self.tax_class = TaxClass.objects.create(
            name="Standard Tax",
            slug="standard-tax",
        )
        self.category = ProductCategory.objects.add_root(
            name="Root Category",
            slug="root-category",
            default_tax_class=self.tax_class,
        )
        self.product = Product.objects.create(
            name="Sample Product",
            slug="sample-product",
            category=self.category,
            tax_class=self.tax_class,
        )

    def test_review_service_uses_feature_flag_helper(self) -> None:
        with mock.patch(
            "apps.reviews.services.reviews_auto_publish_enabled",
            return_value=True,
            create=True,
        ):
            review = ReviewService.submit(
                product=self.product,
                customer=self.customer,
                rating=5,
                draft=ReviewDraft(title="Great", body="Worked well."),
            )

        assert review.is_published
