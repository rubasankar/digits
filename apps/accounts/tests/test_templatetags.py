from __future__ import annotations

from apps.accounts.templatetags.accounts_tags import account_for_provider


class TestAccountForProviderFilter:
    def test_find_matching_provider(self):
        google = type("SocialAccount", (), {"provider": "google"})()
        facebook = type("SocialAccount", (), {"provider": "facebook"})()
        accounts = [google, facebook]
        result = account_for_provider(accounts, "google")
        assert result is google

    def test_no_match(self):
        google = type("SocialAccount", (), {"provider": "google"})()
        result = account_for_provider([google], "facebook")
        assert result is None

    def test_empty_list(self):
        result = account_for_provider([], "google")
        assert result is None

    def test_multiple_matches_returns_first(self):
        g1 = type("SocialAccount", (), {"provider": "google"})()
        g2 = type("SocialAccount", (), {"provider": "google"})()
        result = account_for_provider([g1, g2], "google")
        assert result is g1
