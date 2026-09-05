from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserAccountFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def user(db) -> UserAccountFactory:
    return UserAccountFactory()


@pytest.fixture
def staff_user(db) -> UserAccountFactory:
    from apps.accounts.tests.factories import StaffUserFactory

    return StaffUserFactory()


@pytest.fixture
def superuser(db) -> UserAccountFactory:
    from apps.accounts.tests.factories import SuperUserFactory

    return SuperUserFactory()
