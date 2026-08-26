from __future__ import annotations

from typing import Any

import structlog
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import UserAccount

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=UserAccount)
def deactivate_staff_profile_when_is_staff_revoked(
    sender: type[UserAccount],
    instance: UserAccount,
    **kwargs: Any,
) -> None:
    """Keep StaffProfile.is_active in sync when is_staff is turned off.

    StaffProfile.clean() only guarantees user.is_staff=True at the moment the
    profile itself is saved. Without this, revoking is_staff later on the
    UserAccount leaves a StaffProfile that still reports is_active=True.
    """
    if instance.is_staff:
        return
    profile = getattr(instance, "staff_profile", None)
    if profile is not None and profile.is_active:
        profile.is_active = False
        profile.save(update_fields=["is_active"])
        logger.info(
            "staff.profile_deactivated_on_is_staff_revoked",
            user_id=instance.pk,
            staff_profile_id=profile.pk,
        )
