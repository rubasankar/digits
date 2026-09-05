from __future__ import annotations

import contextlib

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import UserAccount


@receiver(post_save, sender=UserAccount)
def create_profiles_on_user_creation(
    sender: type[UserAccount],
    instance: UserAccount,
    created: bool,  # noqa: FBT001
    **kwargs: object,
) -> None:
    """Create customer/staff profiles on first save."""
    if not created:
        return

    # Check if user is verified before creating profiles
    if not instance.email_verified:
        return

    # Always create a customer profile for every user
    from apps.customers.models import CustomerProfile  # noqa: PLC0415

    with contextlib.suppress(Exception):
        CustomerProfile.objects.get_or_create(
            user=instance,
            defaults={
                "first_name": instance.email.split("@")[0],
                "last_name": "",
            },
        )

    if instance.is_staff:
        from apps.staff.models import StaffProfile  # noqa: PLC0415

        with contextlib.suppress(Exception):
            StaffProfile.objects.get_or_create(
                user=instance,
                defaults={
                    "first_name": instance.email.split("@")[0],
                    "last_name": "",
                },
            )
