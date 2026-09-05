from __future__ import annotations

import factory

from apps.accounts.models import UserAccount


class UserAccountFactory(factory.django.DjangoModelFactory):  # type: ignore[type-arg]
    class Meta:
        model = UserAccount

    email = factory.Sequence(lambda n: f"user{n}@example.com")  # type: ignore[attr-defined]
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation  # type: ignore[attr-defined]
    def password(self, create: bool, extracted: str | None, **kwargs: str) -> None:
        password = extracted or "testpass123!"
        self.set_password(password)  # type: ignore[attr-defined]
        if create:
            self.save(update_fields=["password"])  # type: ignore[attr-defined]


class StaffUserFactory(UserAccountFactory):
    is_staff = True


class SuperUserFactory(UserAccountFactory):
    is_staff = True
    is_superuser = True
