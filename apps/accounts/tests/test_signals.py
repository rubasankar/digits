from __future__ import annotations

import pytest

from apps.accounts.models import UserAccount
from apps.accounts.signals import create_profiles_on_user_creation
from apps.accounts.tests.factories import StaffUserFactory
from apps.accounts.tests.factories import UserAccountFactory


def _verify_email(user: UserAccount) -> None:
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(user=user, email=user.email, verified=True)


def _has_customer_profile(user: UserAccount) -> bool:
    from apps.customers.models import CustomerProfile

    return (
        hasattr(user, "customer_profile")
        or CustomerProfile.objects.filter(user=user).exists()
    )


def _has_staff_profile(user: UserAccount) -> bool:
    from apps.staff.models import StaffProfile

    return StaffProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
class TestCreateProfilesOnUserCreation:
    def test_returns_early_when_instance_not_new(self):
        user = UserAccountFactory(email="late@example.com")
        _verify_email(user)

        create_profiles_on_user_creation(
            sender=UserAccount, instance=user, created=False
        )

        assert not _has_customer_profile(user)
        assert not _has_staff_profile(user)

    def test_no_profiles_created_when_email_not_verified(self):
        user = UserAccountFactory(email="unverified@example.com")

        assert not _has_customer_profile(user)
        assert not _has_staff_profile(user)

    def test_creates_customer_profile_for_verified_email(self):
        from apps.customers.models import CustomerProfile

        user = UserAccountFactory(email="verified@example.com")
        _verify_email(user)

        create_profiles_on_user_creation(
            sender=UserAccount, instance=user, created=True
        )

        profile = CustomerProfile.objects.get(user=user)
        assert profile.first_name == "verified"
        assert profile.last_name == ""

    def test_creates_staff_profile_for_staff_user(self):
        from apps.staff.models import StaffProfile

        user = StaffUserFactory(email="boss@example.com")
        _verify_email(user)

        create_profiles_on_user_creation(
            sender=UserAccount, instance=user, created=True
        )

        profile = StaffProfile.objects.get(user=user)
        assert profile.first_name == "boss"
        assert profile.last_name == ""

    def test_no_staff_profile_for_regular_user(self):
        user = UserAccountFactory(email="normal@example.com")
        _verify_email(user)

        create_profiles_on_user_creation(
            sender=UserAccount, instance=user, created=True
        )

        assert _has_customer_profile(user)
        assert not _has_staff_profile(user)
