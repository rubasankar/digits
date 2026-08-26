from __future__ import annotations

from typing import Any

from django.utils.module_loading import import_string

WAFFLE_SWITCH_NAME = "reviews_auto_publish"

try:
    switch_is_active = import_string("waffle.switch_is_active")
except ImportError:
    switch_is_active = None


def reviews_auto_publish_enabled(request: Any | None = None) -> bool:
    if switch_is_active is None:
        return False

    if request is not None:
        try:
            return bool(switch_is_active(request, WAFFLE_SWITCH_NAME))
        except TypeError:
            return bool(switch_is_active(WAFFLE_SWITCH_NAME))

    try:
        return bool(switch_is_active(WAFFLE_SWITCH_NAME))
    except TypeError:
        return bool(switch_is_active(None, WAFFLE_SWITCH_NAME))
