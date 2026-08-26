from __future__ import annotations

from typing import Any

import structlog
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.shopping.enums import CartType
from apps.shopping.models import Cart
from apps.shopping.service.merge import CartMergeService

logger = structlog.get_logger(__name__)


@receiver(user_logged_in)
def merge_guest_cart_on_login(
    sender: type[Any],
    request: Any,
    user: Any,
    **kwargs: Any,
) -> None:
    """Merge the guest session cart into the customer cart on login."""
    try:
        from apps.customers.models import CustomerProfile  # noqa: PLC0415

        session_key = request.session.session_key
        if not session_key:
            return
        try:
            guest_cart = Cart.objects.get(
                session_key=session_key,
                customer=None,
                cart_type=CartType.ACTIVE,
            )
        except Cart.DoesNotExist:
            return

        try:
            profile: CustomerProfile = user.customer_profile
        except CustomerProfile.DoesNotExist:
            return

        customer_cart, _ = Cart.objects.get_or_create(
            customer=profile,
            cart_type=CartType.ACTIVE,
        )
        CartMergeService().merge(guest_cart, customer_cart)
        logger.info("cart.merged", user_id=user.pk, guest_session=session_key)
    except Exception:
        logger.exception("cart.merge_failed")
