from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import pytest
from django.test import SimpleTestCase

from config.asgi import application


class ASGIHttpRoutingTests(SimpleTestCase):
    def test_http_scope_routed_to_django_application(self) -> None:
        scope = {"type": "http"}
        called_with: list[dict[str, Any]] = []

        async def fake_django(sc: dict[str, Any], recv: Any, snd: Any) -> None:
            called_with.append(sc)
            await recv()
            await snd({"type": "http.response.start"})

        async def receive() -> dict[str, Any]:
            return {}

        async def send(message: dict[str, Any]) -> None:
            pass

        async def _run() -> None:
            with mock.patch("config.asgi.django_application", fake_django):
                await application(scope, receive, send)

        asyncio.run(_run())
        assert called_with == [scope]

    def test_websocket_scope_routed_to_websocket_handler(self) -> None:
        scope = {"type": "websocket"}
        called_with: list[dict[str, Any]] = []

        async def fake_ws(sc: dict[str, Any], recv: Any, snd: Any) -> None:
            called_with.append(sc)
            await recv()
            await snd({"type": "websocket.send", "text": "pong!"})

        async def receive() -> dict[str, Any]:
            return {"type": "websocket.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            pass

        async def _run() -> None:
            with mock.patch("config.asgi.websocket_application", fake_ws):
                await application(scope, receive, send)

        asyncio.run(_run())
        assert called_with == [scope]

    def test_unknown_scope_type_raises_not_implemented(self) -> None:
        scope = {"type": "lifespan"}

        async def receive() -> dict[str, Any]:
            return {}

        async def send(message: dict[str, Any]) -> None:
            pass

        async def _run() -> None:
            await receive()
            await send({})
            await application(scope, receive, send)

        with pytest.raises(NotImplementedError):
            asyncio.run(_run())
