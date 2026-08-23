"""
Custom Django admin configuration for the Unfold admin site.
"""

from typing import TYPE_CHECKING

from django.contrib.admin.apps import AdminConfig
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unfold.sites import UnfoldAdminSite

if TYPE_CHECKING:
    from typing import Any

    from django.http import HttpRequest


class DigitsUnfoldAdminSite(UnfoldAdminSite):  # type: ignore[misc]
    """Project-wide admin site backed by Unfold."""

    index_template = "admin/index.html"

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
