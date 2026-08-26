from __future__ import annotations

from typing import TYPE_CHECKING

from apps.shopping.service.cart import CartService

if TYPE_CHECKING:
    from django.http import HttpRequest


def cart_context(request: HttpRequest) -> dict[str, int]:
    """Inject cart_item_count into every template context."""
    try:
        count = CartService().get_cart_item_count(request)
    except Exception:  # noqa: BLE001
        return {"cart_item_count": 0}
    return {"cart_item_count": count}
