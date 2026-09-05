from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SMSMessage:
    """
    A single SMS to be delivered, independent of any concrete provider.
    """

    to: str
    body: str
    code: str | None = None
