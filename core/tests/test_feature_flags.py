from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.catalogue.models.category import ProductCategory
from apps.catalogue.models.product import Product
from apps.customers.models import CustomerProfile
from apps.pricing.models import TaxClass
from apps.reviews.services import ReviewDraft
from apps.reviews.services import ReviewService

if TYPE_CHECKING:
    from apps.reviews.models import ProductReview

User = get_user_model()


class ReviewAutoPublishFeatureFlagTests(TestCase):
    """Tests that ReviewService respects the reviews_auto_publish Waffle switch."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(email="casey@example.com")
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
            create_kwargs={
                "name": "Root Category",
                "slug": "root-category",
                "default_tax_class": self.tax_class,
            },
        )
        self.product = Product.objects.create(
            name="Sample Product",
            slug="sample-product",
            category=self.category,
            tax_class=self.tax_class,
        )

    def _submit(
        self, rating: int = 5, title: str = "Title", body: str = "Body"
    ) -> ProductReview:
        return ReviewService.submit(
            product=self.product,
            customer=self.customer,
            rating=rating,
            draft=ReviewDraft(title=title, body=body),
        )

    def test_review_published_when_flag_enabled(self) -> None:
        with mock.patch(
            "apps.reviews.services.reviews_auto_publish_enabled",
            return_value=True,
            create=True,
        ):
            review = self._submit()
        assert review.is_published

    def test_review_not_published_when_flag_disabled(self) -> None:
        with mock.patch(
            "apps.reviews.services.reviews_auto_publish_enabled",
            return_value=False,
            create=True,
        ):
            review = self._submit(rating=3, title="OK", body="Average.")
        assert not review.is_published

    def test_review_stored_regardless_of_flag(self) -> None:
        with mock.patch(
            "apps.reviews.services.reviews_auto_publish_enabled",
            return_value=False,
            create=True,
        ):
            review = self._submit(rating=2, title="Meh", body="Not great.")
        assert review.pk is not None


class ReviewsAutoPublishEnabledHelperTests(TestCase):
    """Unit tests for the feature_flags helper itself."""

    def test_returns_false_when_waffle_not_available(self) -> None:
        from apps.reviews.feature_flags import reviews_auto_publish_enabled

        with mock.patch("apps.reviews.feature_flags.switch_is_active", None):
            result = reviews_auto_publish_enabled()
        assert result is False

    def test_returns_true_when_switch_active(self) -> None:
        from apps.reviews.feature_flags import reviews_auto_publish_enabled

        with mock.patch(
            "apps.reviews.feature_flags.switch_is_active",
            return_value=True,
        ):
            result = reviews_auto_publish_enabled()
        assert result is True

    def test_returns_false_when_switch_inactive(self) -> None:
        from apps.reviews.feature_flags import reviews_auto_publish_enabled

        with mock.patch(
            "apps.reviews.feature_flags.switch_is_active",
            return_value=False,
        ):
            result = reviews_auto_publish_enabled()
        assert result is False
