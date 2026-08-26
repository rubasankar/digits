from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast
from unittest import mock

from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory
from django.test import TestCase

from apps.catalogue.models.category import ProductCategory
from apps.catalogue.models.product import Product
from core.views import handler_400
from core.views import handler_403
from core.views import handler_404
from core.views import handler_500

if TYPE_CHECKING:
    from django.http import HttpRequest

# ---------------------------------------------------------------------------
# Home view
# ---------------------------------------------------------------------------


class HomeViewTests(TestCase):
    def _mock_svc(
        self,
        *,
        categories_side_effect: Exception | None = None,
        products_side_effect: Exception | None = None,
    ) -> None:
        patcher = mock.patch("core.views.CatalogueStorefrontService")
        mock_svc = cast("mock.MagicMock", patcher.start())
        self.addCleanup(patcher.stop)
        instance = mock_svc.return_value
        if categories_side_effect:
            instance.get_featured_categories.side_effect = categories_side_effect
        else:
            instance.get_featured_categories.return_value = (
                ProductCategory.objects.none()
            )
        if products_side_effect:
            instance.get_featured_products.side_effect = products_side_effect
        else:
            instance.get_featured_products.return_value = Product.objects.none()

    def test_returns_200(self) -> None:
        self._mock_svc()
        response = self.client.get("/")
        assert response.status_code == 200

    def test_context_contains_featured_categories(self) -> None:
        self._mock_svc()
        response = self.client.get("/")
        assert "featured_categories" in response.context

    def test_context_contains_featured_products(self) -> None:
        self._mock_svc()
        response = self.client.get("/")
        assert "featured_products" in response.context

    def test_swallows_category_service_error_and_still_returns_200(self) -> None:
        self._mock_svc(categories_side_effect=RuntimeError("DB down"))
        response = self.client.get("/")
        assert response.status_code == 200

    def test_swallows_product_service_error_and_still_returns_200(self) -> None:
        self._mock_svc(products_side_effect=RuntimeError("DB down"))
        response = self.client.get("/")
        assert response.status_code == 200

    def test_categories_fallback_to_empty_queryset_on_error(self) -> None:
        self._mock_svc(categories_side_effect=RuntimeError("boom"))
        response = self.client.get("/")
        qs = response.context["featured_categories"]
        assert list(qs) == []

    def test_products_fallback_to_empty_queryset_on_error(self) -> None:
        self._mock_svc(products_side_effect=RuntimeError("boom"))
        response = self.client.get("/")
        qs = response.context["featured_products"]
        assert list(qs) == []


# ---------------------------------------------------------------------------
# Error handler views
# ---------------------------------------------------------------------------


def _get_with_session(path: str = "/") -> HttpRequest:
    """Return a GET request that has an attached session (needed by labb theme tag)."""
    factory = RequestFactory()
    request = factory.get(path)
    session = SessionStore()
    session.create()
    request.session = session
    return request


class Handler400Tests(TestCase):
    def test_status_code(self) -> None:
        response = handler_400(_get_with_session(), exception=None)
        assert response.status_code == 400

    def test_accepts_exception_argument(self) -> None:
        response = handler_400(_get_with_session(), exception=ValueError("bad"))
        assert response.status_code == 400


class Handler403Tests(TestCase):
    def test_status_code(self) -> None:
        response = handler_403(_get_with_session(), exception=None)
        assert response.status_code == 403

    def test_accepts_exception_argument(self) -> None:
        response = handler_403(_get_with_session(), exception=PermissionError("denied"))
        assert response.status_code == 403


class Handler404Tests(TestCase):
    def test_status_code(self) -> None:
        response = handler_404(_get_with_session(), exception=None)
        assert response.status_code == 404

    def test_accepts_exception_argument(self) -> None:
        response = handler_404(_get_with_session(), exception=LookupError("missing"))
        assert response.status_code == 404


class Handler500Tests(TestCase):
    def test_status_code(self) -> None:
        # handler_500 uses render_to_string (no context processors), no session needed.
        factory = RequestFactory()
        response = handler_500(factory.get("/"))
        assert response.status_code == 500

    def test_returns_non_empty_content(self) -> None:
        factory = RequestFactory()
        response = handler_500(factory.get("/"))
        assert len(response.content) > 0
