"""Live shop queues over WebSocket: the shop's own screen and the public board in the shop.

Each shop with open sockets has one room per view (the shop's full line, or the masked board). A room's
refresher builds the snapshot when something changed and sends it only if its version differs from the
last one sent, so screens get diffs of the whole line, never a stream of identical frames:

- poke(shop_id) after any change to the line in this process (a booking made, started, cancelled, a
  walk-in, a reorder, a break) refreshes at once;
- with QUEUE_PUBSUB on, the poke is also published on Redis (queue:{shop_id}) so the rooms on every
  replica refresh; otherwise, and as a safety net, every room refreshes every REFRESH_SECONDS (a wait
  that only time changes, such as someone overrunning, moves on its own).

Backpressure: a socket that does not take a frame within SEND_TIMEOUT is closed (the client reconnects
and gets the current snapshot); at most MAX_PER_ROOM sockets per room. Clients reconnect with backoff and
can send "ping" (answered "pong") to keep idle connections open through proxies.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, Optional, Set, Tuple

import structlog
from fastapi import WebSocket

from app.config import settings

log = structlog.get_logger()

REFRESH_SECONDS = 15.0
SEND_TIMEOUT = 5.0
MAX_PER_ROOM = 50
CHANNEL = "queue:"

# Builds a room's snapshot: (version, payload). Called with no arguments; it opens its own session.
Build = Callable[[], Awaitable[Tuple[str, dict]]]


@dataclass
class Room:
    build: Build
    sockets: Set[WebSocket] = field(default_factory=set)
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    version: Optional[str] = None
    payload: Optional[dict] = None
    task: Optional[asyncio.Task] = None


class QueueHub:
    def __init__(self):
        self.rooms: Dict[Tuple[str, str], Room] = {}
        self._listener: Optional[asyncio.Task] = None
        self._redis = None

    async def join(self, shop_id: str, view: str, websocket: WebSocket, build: Build) -> bool:
        """Adds an accepted socket to the shop's room for [view] and sends it the current snapshot."""
        key = (shop_id, view)
        room = self.rooms.get(key)
        if room is None:
            room = self.rooms[key] = Room(build)
        if len(room.sockets) >= MAX_PER_ROOM:
            await websocket.close(code=1013)
            return False
        room.sockets.add(websocket)
        if room.payload is None:
            room.version, room.payload = await build()
        await self._send(room, websocket, room.payload)
        if room.task is None or room.task.done():
            room.task = asyncio.create_task(self._refresh(key, room))
        self._listen()
        return True

    def leave(self, shop_id: str, view: str, websocket: WebSocket) -> None:
        room = self.rooms.get((shop_id, view))
        if room is None:
            return
        room.sockets.discard(websocket)
        if not room.sockets:
            if room.task:
                room.task.cancel()
            self.rooms.pop((shop_id, view), None)

    def poke(self, shop_id: Optional[str]) -> None:
        """The shop's line changed: its rooms here refresh now, and on other replicas through Redis."""
        if not shop_id:
            return
        self._wake(shop_id)
        if settings.QUEUE_PUBSUB:
            asyncio.get_running_loop().create_task(self._publish(shop_id))

    def _wake(self, shop_id: str) -> None:
        for (sid, _), room in list(self.rooms.items()):
            if sid == shop_id:
                room.changed.set()

    async def _refresh(self, key, room: Room) -> None:
        while room.sockets:
            try:
                await asyncio.wait_for(room.changed.wait(), timeout=REFRESH_SECONDS)
            except asyncio.TimeoutError:
                pass
            room.changed.clear()
            try:
                version, payload = await room.build()
            except Exception as e:  # a failed build keeps the last snapshot; the next try may work
                log.warning("queue_hub_build_failed", shop_id=key[0], view=key[1], error=str(e))
                continue
            if version == room.version:
                continue
            room.version, room.payload = version, payload
            await asyncio.gather(*(self._send(room, ws, payload) for ws in list(room.sockets)))

    async def _send(self, room: Room, websocket: WebSocket, payload: dict) -> None:
        try:
            await asyncio.wait_for(websocket.send_json(payload), timeout=SEND_TIMEOUT)
        except Exception:  # slow or gone: drop it; the client reconnects and gets the latest
            room.sockets.discard(websocket)
            try:
                await websocket.close(code=1013)
            except Exception:
                pass

    async def _publish(self, shop_id: str) -> None:
        try:
            await self._client().publish(CHANNEL + shop_id, "1")
        except Exception as e:
            log.warning("queue_hub_publish_failed", error=str(e))

    def _client(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(settings.REDIS_URL)
        return self._redis

    def _listen(self) -> None:
        if not settings.QUEUE_PUBSUB or (self._listener and not self._listener.done()):
            return
        self._listener = asyncio.get_running_loop().create_task(self._subscribe())

    async def _subscribe(self) -> None:
        """Pokes from other replicas wake this one's rooms (reconnecting after a Redis outage)."""
        while self.rooms:
            try:
                pubsub = self._client().pubsub()
                await pubsub.psubscribe(CHANNEL + "*")
                async for message in pubsub.listen():
                    if message.get("type") == "pmessage":
                        channel = message["channel"]
                        channel = channel.decode() if isinstance(channel, bytes) else channel
                        self._wake(channel[len(CHANNEL) :])
                    if not self.rooms:
                        break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("queue_hub_subscribe_failed", error=str(e))
                await asyncio.sleep(5)


hub = QueueHub()


def version_of(payload) -> str:
    """A short fingerprint of a snapshot: equal snapshots, equal versions."""
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]
