import asyncio
import json
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class EmpireEventBus:
    """
    Barramento Híbrido Redis Streams/PubSub + AsyncIO Broadcast.
    Alimenta WebSockets do Painel ADM em tempo real (<15ms) e mantém histórico em ring-buffer.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=150)
        self._redis_url = os.getenv("REDIS_URL")
        self._redis_client = None

    async def connect_redis_if_available(self) -> None:
        if self._redis_url and aioredis is not None:
            try:
                client = aioredis.from_url(self._redis_url, decode_responses=True)
                await client.ping()
                self._redis_client = client
            except Exception:
                self._redis_client = None

    async def publish(
        self,
        event_type: str,
        agent_slug: str,
        message: str,
        level: str = "INFO",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": f"evt-{uuid.uuid4().hex[:10]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "agent": agent_slug,
            "level": level,
            "message": message,
            "payload": payload or {},
        }
        self._history.append(event)

        if self._redis_client is not None:
            try:
                await self._redis_client.xadd(
                    "empire:telemetry:stream",
                    {"data": json.dumps(event)},
                    maxlen=1000,
                )
                await self._redis_client.publish("empire:telemetry:pubsub", json.dumps(event))
            except Exception:
                pass

        dead_queues = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(q)

        for dq in dead_queues:
            self._subscribers.discard(dq)

        return event

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=250)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def recent_events(self, limit: int = 60) -> list[dict[str, Any]]:
        items = list(self._history)
        return items[-limit:]


event_bus = EmpireEventBus()
