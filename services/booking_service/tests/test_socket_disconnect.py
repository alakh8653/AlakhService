"""A client hanging up at any moment ends its socket quietly, rather than logging a crash."""

import pytest
from starlette.websockets import WebSocketDisconnect, WebSocketDisconnected

from app.routers import queue


class FakeSocket:
    def __init__(self, error):
        self.error = error
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def receive_text(self):
        raise self.error


class FakeHub:
    def __init__(self):
        self.left = []

    async def join(self, shop_id, view, websocket, build):
        return True

    def leave(self, shop_id, view, websocket):
        self.left.append((shop_id, view))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [WebSocketDisconnect(code=1000), WebSocketDisconnected("WebSocket is not connected.")]
)
async def test_hanging_up_leaves_the_room_without_an_error(monkeypatch, error):
    hub = FakeHub()
    monkeypatch.setattr(queue, "hub", hub)
    await queue._live(FakeSocket(error), "shop-1", "shop", None)
    assert hub.left == [("shop-1", "shop")]
