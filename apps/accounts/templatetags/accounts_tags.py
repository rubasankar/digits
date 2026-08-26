from __future__ import annotations

from typing import TYPE_CHECKING

from django import template

if TYPE_CHECKING:
    from allauth.socialaccount.models import SocialAccount

register = template.Library()


@register.filter
def account_for_provider(
    accounts: list[SocialAccount], provider_id: str
) -> SocialAccount | None:
    """Return the connected SocialAccount for a provider id, or None."""
    for account in accounts:
        if account.provider == provider_id:
            return account
    return None
