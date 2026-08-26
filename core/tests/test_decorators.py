from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import TestCase

from apps.customers.models import CustomerProfile

User = get_user_model()


class RequireCustomerDecoratorTests(TestCase):
    """
    Tests for core.decorators.require_customer.

    The decorator is login_required(login_url="account_login").
    We exercise it via the customers dashboard (/account/) which is
    decorated with require_customer, confirming that:
      - anonymous requests are sent to the login page
      - authenticated requests pass through the decorator
        (the view may still redirect after that for its own reasons,
        but the redirect will not point at the login URL)
    """

    def test_anonymous_user_is_redirected(self) -> None:
        response = self.client.get("/account/")
        assert response.status_code in (301, 302)

    def test_anonymous_redirect_points_to_login(self) -> None:
        response = self.client.get("/account/")
        assert isinstance(response, HttpResponseRedirect)
        assert "/auth/" in response.url or "login" in response.url

    def test_anonymous_redirect_includes_next_param(self) -> None:
        response = self.client.get("/account/")
        assert isinstance(response, HttpResponseRedirect)
        assert "next=" in response.url

    def test_authenticated_user_passes_decorator(self) -> None:
        """
        With a CustomerProfile present the dashboard renders (200).
        Without one the view itself redirects to profile_edit - but that
        redirect must NOT point to the login URL, confirming the decorator
        let the user through.
        """
        user = User.objects.create_user(
            email="shopper@example.com",
            password="pass1234!",
        )
        CustomerProfile.objects.create(
            user=user,
            first_name="Shop",
            last_name="Per",
        )
        self.client.force_login(user)
        response = self.client.get("/account/")
        # The decorator passed - response is a 200 (dashboard rendered).
        assert response.status_code == 200

    def test_authenticated_without_profile_gets_non_login_redirect(self) -> None:
        """Decorator passes; the view redirects to profile_edit, not login."""
        user = User.objects.create_user(
            email="noprofile@example.com",
            password="pass1234!",
        )
        self.client.force_login(user)
        response = self.client.get("/account/")
        # Could be 200 or a redirect to profile_edit - either way not the login page.
        if response.status_code in (301, 302):
            assert isinstance(response, HttpResponseRedirect)
            assert "login" not in response.url
            assert "/auth/" not in response.url
