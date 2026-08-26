from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from config.settings.apps.unfold import badge_reviews_pending
from config.settings.apps.unfold import dashboard_callback
from config.settings.apps.unfold import environment_callback
from config.settings.apps.unfold import tabs_callback

if TYPE_CHECKING:
    from django.http import HttpRequest


def _request() -> HttpRequest:
    factory = RequestFactory()
    return factory.get("/admin/")


# ---------------------------------------------------------------------------
# environment_callback
# ---------------------------------------------------------------------------


class EnvironmentCallbackTests(TestCase):
    def test_debug_true_returns_development_warning(self) -> None:
        with override_settings(DEBUG=True):
            result = environment_callback(_request())
        assert result[1] == "warning"
        assert "development" in result[0].lower()

    def test_debug_false_returns_production_danger(self) -> None:
        with override_settings(DEBUG=False):
            result = environment_callback(_request())
        assert result[1] == "danger"
        assert "production" in result[0].lower()

    def test_returns_list_of_two_items(self) -> None:
        result = environment_callback(_request())
        assert isinstance(result, list)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# badge_reviews_pending
#
# ProductReview is imported inside badge_reviews_pending, so patch the
# class on its real home module, not on the settings module.
# ---------------------------------------------------------------------------


class BadgeReviewsPendingTests(TestCase):
    _TARGET = "apps.reviews.models.ProductReview"

    def test_returns_zero_when_no_reviews(self) -> None:
        with mock.patch(self._TARGET) as mock_review:
            mock_review.objects.filter.return_value.count.return_value = 0
            result = badge_reviews_pending(_request())
        assert result == 0

    def test_returns_count_of_unpublished_reviews(self) -> None:
        expected = 7
        with mock.patch(self._TARGET) as mock_review:
            mock_review.objects.filter.return_value.count.return_value = expected
            result = badge_reviews_pending(_request())
        assert result == expected

    def test_filters_by_is_published_false(self) -> None:
        with mock.patch(self._TARGET) as mock_review:
            mock_review.objects.filter.return_value.count.return_value = 3
            badge_reviews_pending(_request())
        mock_review.objects.filter.assert_called_once_with(is_published=False)


# ---------------------------------------------------------------------------
# dashboard_callback
#
# Same principle: patch each model on its real home module.
# ---------------------------------------------------------------------------


class DashboardCallbackTests(TestCase):
    def _patched_callback(self, counts: dict[str, int]) -> dict[str, object]:
        with (
            mock.patch("apps.catalogue.models.Product") as mock_product,
            mock.patch("apps.orders.models.Order") as mock_order,
            mock.patch("apps.customers.models.CustomerProfile") as mock_customer,
            mock.patch("apps.reviews.models.ProductReview") as mock_review,
        ):
            mock_product.objects.count.return_value = counts.get("products", 0)
            mock_order.objects.count.return_value = counts.get("orders", 0)
            mock_customer.objects.count.return_value = counts.get("customers", 0)
            mock_review.objects.filter.return_value.count.return_value = counts.get(
                "reviews", 0
            )
            return dashboard_callback(_request(), {})

    def test_returns_context_with_total_products(self) -> None:
        expected = 42
        ctx = self._patched_callback({"products": expected})
        assert ctx["total_products"] == expected

    def test_returns_context_with_total_orders(self) -> None:
        expected = 10
        ctx = self._patched_callback({"orders": expected})
        assert ctx["total_orders"] == expected

    def test_returns_context_with_total_customers(self) -> None:
        expected = 5
        ctx = self._patched_callback({"customers": expected})
        assert ctx["total_customers"] == expected

    def test_returns_context_with_pending_reviews(self) -> None:
        expected = 3
        ctx = self._patched_callback({"reviews": expected})
        assert ctx["pending_reviews"] == expected

    def test_existing_context_keys_preserved(self) -> None:
        ctx = self._patched_callback({})
        ctx["existing_key"] = "value"
        assert ctx["existing_key"] == "value"


# ---------------------------------------------------------------------------
# tabs_callback
# ---------------------------------------------------------------------------


class TabsCallbackTests(TestCase):
    def test_returns_empty_list_when_no_resolver_match(self) -> None:
        result = tabs_callback(_request())
        assert result == []

    def test_returns_empty_list_when_no_object_id(self) -> None:
        request = _request()
        resolver = mock.MagicMock()
        resolver.kwargs = {}
        request.resolver_match = resolver
        result = tabs_callback(request)
        assert result == []

    def test_returns_tabs_when_object_id_present(self) -> None:
        request = _request()
        resolver = mock.MagicMock()
        resolver.kwargs = {"object_id": "abc-123"}
        resolver.view_name = "admin:catalogue_product_change"
        request.resolver_match = resolver

        change_url = "/admin/catalogue/product/abc-123/change/"
        with mock.patch("config.settings.apps.unfold.reverse", return_value=change_url):
            result = tabs_callback(request)

        assert len(result) == 1
        tab_titles = [str(item["title"]) for item in result[0]["items"]]
        assert any("General" in t for t in tab_titles)
        assert any("Variants" in t for t in tab_titles)
        assert any("SEO" in t for t in tab_titles)

    def test_tabs_contain_models_key(self) -> None:
        request = _request()
        resolver = mock.MagicMock()
        resolver.kwargs = {"object_id": "abc-123"}
        resolver.view_name = "admin:catalogue_product_change"
        request.resolver_match = resolver

        with mock.patch("config.settings.apps.unfold.reverse", return_value="/change/"):
            result = tabs_callback(request)

        assert "models" in result[0]
        assert "catalogue.product" in result[0]["models"]
