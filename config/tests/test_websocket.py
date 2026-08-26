from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from django.test import SimpleTestCase

from config.websocket import websocket_application


def _make_receive(*events: dict[str, Any]):  # type: ignore[no-untyped-def]
    """Return an async callable that yields events in order, then disconnects."""
    queue: deque[dict[str, Any]] = deque(events)

    async def receive() -> dict[str, Any]:
        if queue:
            return queue.popleft()
        return {"type": "websocket.disconnect"}

    return receive


class _Sender:
    """Collects all outgoing websocket messages."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.sent.append(message)


def _run(*events: dict[str, Any]) -> list[dict[str, Any]]:
    """Run the websocket handler with the given events and return sent messages."""
    sender = _Sender()
    receive = _make_receive(*events)
    asyncio.run(websocket_application({}, receive, sender))
    return sender.sent


class WebsocketConnectTests(SimpleTestCase):
    def test_connect_sends_accept(self) -> None:
        sent = _run(
            {"type": "websocket.connect"},
            {"type": "websocket.disconnect"},
        )
        types = [m["type"] for m in sent]
        assert "websocket.accept" in types


class WebsocketPingPongTests(SimpleTestCase):
    def test_ping_receives_pong(self) -> None:
        sent = _run(
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "ping"},
            {"type": "websocket.disconnect"},
        )
        texts = [m.get("text") for m in sent if m.get("type") == "websocket.send"]
        assert "pong!" in texts

    def test_non_ping_message_sends_nothing_back(self) -> None:
        sent = _run(
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "hello"},
            {"type": "websocket.disconnect"},
        )
        send_events = [m for m in sent if m.get("type") == "websocket.send"]
        assert send_events == []

    def test_multiple_pings_get_multiple_pongs(self) -> None:
        sent = _run(
            {"type": "websocket.connect"},
            {"type": "websocket.receive", "text": "ping"},
            {"type": "websocket.receive", "text": "ping"},
            {"type": "websocket.disconnect"},
        )
        pongs = [
            m
            for m in sent
            if m.get("type") == "websocket.send" and m.get("text") == "pong!"
        ]
        assert len(pongs) == 2


class WebsocketDisconnectTests(SimpleTestCase):
    def test_disconnect_stops_loop(self) -> None:
        # Must complete without hanging.
        sent = _run({"type": "websocket.disconnect"})
        # No messages expected after an immediate disconnect.
        assert all(m.get("type") != "websocket.send" for m in sent)
