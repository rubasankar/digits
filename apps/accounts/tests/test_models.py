from __future__ import annotations

import pytest

from apps.accounts.models import UserAccount
from apps.accounts.tests.factories import UserAccountFactory


@pytest.mark.django_db
class TestUserAccountModel:
    def test_create_user(self):
        user = UserAccountFactory(email="test@example.com")
        assert user.pk is not None
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_str(self):
        user = UserAccountFactory(email="test@example.com")
        assert str(user) == "test@example.com"

    def test_repr(self):
        user = UserAccountFactory(email="test@example.com")
        r = repr(user)
        assert "UserAccount" in r
        assert "test@example.com" in r

    def test_username_field_is_email(self):
        assert UserAccount.USERNAME_FIELD == "email"

    def test_required_fields_empty(self):
        assert UserAccount.REQUIRED_FIELDS == []

    def test_email_unique(self):
        UserAccountFactory(email="test@example.com")
        with pytest.raises(Exception):
            UserAccountFactory(email="test@example.com")

    def test_is_customer_false_without_profile(self):
        user = UserAccountFactory()
        assert user.is_customer is False

    def test_is_customer_true_with_profile(self):
        from apps.customers.models import CustomerProfile

        user = UserAccountFactory()
        CustomerProfile.objects.create(user=user, first_name="Test")
        assert user.is_customer is True

    def test_is_store_staff_false_without_profile(self):
        user = UserAccountFactory()
        assert user.is_store_staff is False

    def test_is_store_staff_true_with_profile(self):
        from apps.accounts.tests.factories import StaffUserFactory
        from apps.staff.models import StaffProfile

        staff_user = StaffUserFactory()
        StaffProfile.objects.create(user=staff_user, first_name="Staff")
        assert staff_user.is_store_staff is True

    def test_get_full_name_fallback_to_email(self):
        user = UserAccountFactory(email="john@example.com")
        assert user.get_full_name() == "john"

    def test_get_full_name_from_customer_profile(self):
        from apps.customers.models import CustomerProfile

        user = UserAccountFactory()
        CustomerProfile.objects.create(user=user, first_name="John", last_name="Doe")
        assert user.get_full_name() == "John Doe"

    def test_get_full_name_from_staff_profile(self):
        from apps.accounts.tests.factories import StaffUserFactory
        from apps.staff.models import StaffProfile

        staff_user = StaffUserFactory()
        StaffProfile.objects.create(
            user=staff_user, first_name="Jane", last_name="Smith"
        )
        assert staff_user.get_full_name() == "Jane Smith"

    def test_get_short_name(self):
        user = UserAccountFactory(email="test@example.com")
        assert user.get_short_name() == user.get_full_name()

    def test_avatar_url_empty(self):
        user = UserAccountFactory()
        assert user.avatar_url == ""

    def test_avatar_url_returns_customer_avatar(self, user):
        from apps.customers.models import CustomerProfile

        profile = CustomerProfile.objects.create(user=user, first_name="Test")
        profile.avatar.name = "avatars/customers/customer.png"
        profile.save(update_fields=["avatar"])
        assert user.avatar_url.endswith("avatars/customers/customer.png")

    def test_avatar_url_returns_staff_avatar(self, user):
        from apps.staff.models import StaffProfile

        profile = StaffProfile.objects.create(user=user, first_name="Staff")
        profile.avatar.name = "avatars/staff/staff.png"
        profile.save(update_fields=["avatar"])
        assert user.avatar_url.endswith("avatars/staff/staff.png")

    def test_avatar_url_prefers_staff_avatar_over_customer(self, user):
        from apps.customers.models import CustomerProfile
        from apps.staff.models import StaffProfile

        customer = CustomerProfile.objects.create(user=user, first_name="Test")
        customer.avatar.name = "avatars/customers/customer.png"
        customer.save(update_fields=["avatar"])

        staff = StaffProfile.objects.create(user=user, first_name="Staff")
        staff.avatar.name = "avatars/staff/staff.png"
        staff.save(update_fields=["avatar"])

        assert user.avatar_url.endswith("avatars/staff/staff.png")
