from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.checkout.enums import CheckoutStep
from apps.checkout.models import CheckoutSession
from apps.checkout.service.checkout import _STEP_URL_MAP
from apps.checkout.service.checkout import STEP_ORDER
from apps.shopping.service.cart import CartService

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse


def require_checkout_step(
    required_step: str,
) -> Callable[[Callable[..., HttpResponse]], Callable[..., HttpResponse]]:
    """Decorate a checkout view to enforce step order and session validity.

    Redirects to cart when the session is expired or missing.
    Redirects to the current step when the visitor tries to jump ahead.
    """

    def decorator(
        view_func: Callable[..., HttpResponse],
    ) -> Callable[..., HttpResponse]:
        @functools.wraps(view_func)
        def wrapper(
            request: HttpRequest,
            *args: object,
            **kwargs: object,
        ) -> HttpResponse:
            cart = CartService().get_or_create_cart(request)

            try:
                session = CheckoutSession.objects.get(cart=cart)
            except CheckoutSession.DoesNotExist:
                messages.info(
                    request,
                    str(_("Please start checkout from your cart.")),
                )
                return redirect("shopping:cart")

            if session.expires_at and timezone.now() > session.expires_at:
                messages.warning(
                    request,
                    str(_("Your checkout session has expired. Please start again.")),
                )
                return redirect("shopping:cart")

            current_idx = STEP_ORDER.index(CheckoutStep(session.step))
            required_idx = STEP_ORDER.index(CheckoutStep(required_step))

            if required_idx > current_idx:
                current_url = _STEP_URL_MAP[CheckoutStep(session.step)]
                return redirect(current_url)

            return view_func(request, *args, session=session, **kwargs)

        return wrapper

    return decorator
