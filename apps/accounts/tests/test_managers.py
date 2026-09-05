from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserManager:
    def test_create_user(self):
        user = User.objects.create_user(email="test@example.com", password="pass1234")
        assert user.pk is not None
        assert user.check_password("pass1234")
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_user_no_email_raises(self):
        with pytest.raises(ValueError, match="email must be set"):
            User.objects.create_user(email="", password="pass1234")

    def test_create_user_with_extra_fields(self):
        user = User.objects.create_user(
            email="test@example.com",
            password="pass1234",
            is_active=False,
        )
        assert user.is_active is False

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com", password="pass1234"
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.check_password("pass1234")

    def test_create_superuser_is_staff_false_raises(self):
        with pytest.raises(ValueError, match="is_staff=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="pass1234",
                is_staff=False,
            )

    def test_create_superuser_is_superuser_false_raises(self):
        with pytest.raises(ValueError, match="is_superuser=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="pass1234",
                is_superuser=False,
            )

    def test_get_by_natural_key(self):
        user = User.objects.create_user(email="test@example.com", password="pass1234")
        found = User.objects.get_by_natural_key("test@example.com")
        assert found.pk == user.pk

    def test_email_normalized(self):
        user = User.objects.create_user(email="TEST@EXAMPLE.COM", password="pass1234")
        assert user.email == "test@example.com"
