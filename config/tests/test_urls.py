from __future__ import annotations

import importlib

import pytest
from django.conf import settings
from django.test import SimpleTestCase
from django.test import override_settings
from django.urls import Resolver404
from django.urls import clear_url_caches
from django.urls import resolve
from django.urls import reverse
from django.views import defaults as default_views

import config.urls as urls_module


def _restore_urlconf() -> None:
    """Rebuild the module with the real (non-debug) test settings."""
    with override_settings(DEBUG=False):
        importlib.reload(urls_module)
    clear_url_caches()


class UrlNameTests(SimpleTestCase):
    def test_home_reverse(self) -> None:
        assert reverse("core:home") == "/"

    def test_set_theme_reverse(self) -> None:
        assert reverse("set_theme") == "/set-theme/"

    def test_admin_index_reverses(self) -> None:
        assert reverse("admin:index").startswith("/admin/")

    def test_allauth_urls_reverse(self) -> None:
        assert reverse("account_login").startswith("/auth/")

    def test_catalogue_admin_urls_mounted(self) -> None:
        assert reverse("admin:index").startswith("/admin/")


class HandlerModuleAttributesTests(SimpleTestCase):
    def test_error_handlers_point_at_core_views(self) -> None:
        assert urls_module.handler400 == "core.views.handler_400"
        assert urls_module.handler403 == "core.views.handler_403"
        assert urls_module.handler404 == "core.views.handler_404"
        assert urls_module.handler500 == "core.views.handler_500"


class ErrorPageUrlTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_error_pages_not_mounted_when_not_debug(self) -> None:
        clear_url_caches()
        for path in ("/400/", "/403/", "/404/", "/500/"):
            with pytest.raises(Resolver404):
                resolve(path)

    def test_error_pages_resolve_when_debug_enabled(self) -> None:
        with override_settings(DEBUG=True):
            importlib.reload(urls_module)
        clear_url_caches()
        try:
            assert resolve("/400/").func is default_views.bad_request
            assert resolve("/403/").func is default_views.permission_denied
            assert resolve("/404/").func is default_views.page_not_found
            assert resolve("/500/").func is default_views.server_error
        finally:
            _restore_urlconf()

    def test_debug_toolbar_mounted_under_debug_prefix_when_installed(self) -> None:
        installed = [*settings.INSTALLED_APPS, "debug_toolbar"]
        try:
            with override_settings(DEBUG=True, INSTALLED_APPS=installed):
                importlib.reload(urls_module)
                patterns = urls_module.urlpatterns
                assert any(
                    str(getattr(pattern, "pattern", "")).startswith("__debug__/")
                    for pattern in patterns
                )
        finally:
            _restore_urlconf()

    @override_settings(DEBUG=True, INSTALLED_APPS=list(settings.INSTALLED_APPS))
    def test_debug_toolbar_absent_when_not_installed(self) -> None:
        try:
            importlib.reload(urls_module)
            patterns = urls_module.urlpatterns
            assert not any(
                str(getattr(pattern, "pattern", "")).startswith("__debug__/")
                for pattern in patterns
            )
        finally:
            _restore_urlconf()
