"""
Custom Django admin configuration for the Unfold admin site.
"""
# ruff: noqa: PLC0415
# mypy: disable-error-code=misc

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.sites import UnfoldAdminSite

if TYPE_CHECKING:
    from typing import Any

    from django.http import HttpRequest


class DigitsUnfoldAdminSite(UnfoldAdminSite):
    """Project-wide admin site backed by Unfold."""

    index_template = "admin/index.html"

    def has_permission(self, request: HttpRequest) -> bool:
        if not super().has_permission(request):
            return False
        # StaffProfile.is_active is documented as an additional access gate
        # alongside UserAccount.is_active/is_staff -- enforce it here since
        # Django's default admin permission check never looks at it.
        profile = getattr(request.user, "staff_profile", None)
        return profile is None or profile.is_active

    def _get_account_links(self, request: HttpRequest) -> list[dict[str, Any]]:
        links: list[dict[str, Any]] = []

        profile = getattr(request.user, "staff_profile", None)
        if profile is not None:
            links.append(
                {
                    "title": _("My profile"),
                    "link": reverse(
                        "admin:staff_staffprofile_change", args=[profile.pk]
                    ),
                }
            )

        links.append(
            {"title": _("Change password"), "link": reverse("admin:password_change")}
        )
        return links


class DigitsAdminConfig(AdminConfig):
    default_site = "config.admin.DigitsUnfoldAdminSite"

    def ready(self) -> None:
        super().ready()
        _register_waffle_admin()


def _register_waffle_admin() -> None:
    """Unregister default waffle admin classes and re-register with Unfold."""
    from unfold.admin import ModelAdmin
    from unfold.contrib.waffle.admin import FlagAdmin as BaseFlagAdmin
    from waffle.admin import SampleAdmin as BaseSampleAdmin
    from waffle.admin import SwitchAdmin as BaseSwitchAdmin
    from waffle.models import Flag
    from waffle.models import Sample
    from waffle.models import Switch

    admin.site.unregister(Flag)
    admin.site.unregister(Switch)
    admin.site.unregister(Sample)

    @admin.register(Flag)
    class FlagAdmin(BaseFlagAdmin):
        pass

    @admin.register(Switch)
    class SwitchAdmin(ModelAdmin, BaseSwitchAdmin):
        pass

    @admin.register(Sample)
    class SampleAdmin(ModelAdmin, BaseSampleAdmin):
        pass
