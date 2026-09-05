from __future__ import annotations

import pytest

from apps.accounts.tests.factories import UserAccountFactory
from apps.staff.models import StaffProfile


@pytest.mark.django_db
class TestStaffSignals:
    def test_deactivate_profile_when_is_staff_revoked(self):
        staff_user = UserAccountFactory(is_staff=True)
        profile = StaffProfile.objects.create(
            user=staff_user, first_name="Staff", is_active=True
        )

        staff_user.is_staff = False
        staff_user.save(update_fields=["is_staff"])

        profile.refresh_from_db()
        assert profile.is_active is False

    def test_profile_not_deactivated_when_is_staff_true(self):
        staff_user = UserAccountFactory(is_staff=True)
        profile = StaffProfile.objects.create(
            user=staff_user, first_name="Staff", is_active=True
        )

        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])

        profile.refresh_from_db()
        assert profile.is_active is True

    def test_no_error_when_no_profile(self):
        user = UserAccountFactory(is_staff=True)
        user.is_staff = False
        user.save(update_fields=["is_staff"])

    def test_already_inactive_profile_not_affected(self):
        staff_user = UserAccountFactory(is_staff=True)
        profile = StaffProfile.objects.create(
            user=staff_user, first_name="Staff", is_active=False
        )

        staff_user.is_staff = False
        staff_user.save(update_fields=["is_staff"])

        profile.refresh_from_db()
        assert profile.is_active is False
