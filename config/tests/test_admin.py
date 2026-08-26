from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from apps.staff.models import StaffDepartment
from apps.staff.models import StaffProfile
from config.admin import DigitsUnfoldAdminSite

if TYPE_CHECKING:
    from django.http import HttpRequest

User = get_user_model()


def _make_site() -> DigitsUnfoldAdminSite:
    return DigitsUnfoldAdminSite(name="test_admin")


def _make_request(user: object) -> HttpRequest:
    factory = RequestFactory()
    request = factory.get("/admin/")
    request.user = user  # type: ignore[assignment]
    return request


class HasPermissionTests(TestCase):
    """DigitsUnfoldAdminSite.has_permission enforces staff_profile.is_active."""

    def _staff_user(self) -> object:
        return User.objects.create_user(
            email="staff@example.com",
            password="pass1234!",
            is_staff=True,
            is_active=True,
        )

    def test_non_staff_user_denied(self) -> None:
        user = User.objects.create_user(
            email="plain@example.com",
            password="pass1234!",
            is_staff=False,
        )
        site = _make_site()
        request = _make_request(user)
        assert not site.has_permission(request)

    def test_staff_user_without_profile_allowed(self) -> None:
        user = self._staff_user()
        site = _make_site()
        request = _make_request(user)
        assert site.has_permission(request)

    def test_staff_user_with_active_profile_allowed(self) -> None:
        user = self._staff_user()
        dept = StaffDepartment.objects.create(name="Ops")
        StaffProfile.objects.create(
            user=user,  # type: ignore[misc]
            first_name="Alice",
            is_active=True,
            department=dept,
        )
        site = _make_site()
        request = _make_request(user)
        assert site.has_permission(request)

    def test_staff_user_with_inactive_profile_denied(self) -> None:
        user = self._staff_user()
        dept = StaffDepartment.objects.create(name="Ops2")
        StaffProfile.objects.create(
            user=user,  # type: ignore[misc]
            first_name="Bob",
            is_active=False,
            department=dept,
        )
        site = _make_site()
        request = _make_request(user)
        assert not site.has_permission(request)

    def test_inactive_user_account_denied(self) -> None:
        user = User.objects.create_user(
            email="inactive@example.com",
            password="pass1234!",
            is_staff=True,
            is_active=False,
        )
        site = _make_site()
        request = _make_request(user)
        assert not site.has_permission(request)


class GetAccountLinksTests(TestCase):
    """DigitsUnfoldAdminSite._get_account_links builds conditional link lists."""

    def _staff_user(self) -> object:
        return User.objects.create_user(
            email="links@example.com",
            password="pass1234!",
            is_staff=True,
        )

    def test_always_includes_change_password_link(self) -> None:
        user = self._staff_user()
        site = _make_site()
        request = _make_request(user)
        links = site._get_account_links(request)
        titles = [link["title"] for link in links]
        assert any("password" in str(t).lower() for t in titles)

    def test_includes_my_profile_when_staff_profile_exists(self) -> None:
        user = self._staff_user()
        dept = StaffDepartment.objects.create(name="HR")
        StaffProfile.objects.create(
            user=user,  # type: ignore[misc]
            first_name="Carol",
            is_active=True,
            department=dept,
        )
        site = _make_site()
        request = _make_request(user)
        links = site._get_account_links(request)
        titles = [str(link["title"]) for link in links]
        assert any("profile" in t.lower() for t in titles)

    def test_no_profile_link_when_staff_profile_absent(self) -> None:
        user = self._staff_user()
        site = _make_site()
        request = _make_request(user)
        links = site._get_account_links(request)
        titles = [str(link["title"]) for link in links]
        assert not any("profile" in t.lower() for t in titles)
