from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class EventMessage:
    event: str
    data: Dict[str, Any]


class EventBroker:
    """Very small in-memory pub/sub broker for SSE.

    Note: This is single-process only. For multi-worker deployments, swap to Redis pub/sub.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[queue.Queue[EventMessage]] = set()

    def subscribe(self) -> queue.Queue[EventMessage]:
        q: queue.Queue[EventMessage] = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[EventMessage]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        msg = EventMessage(event=event, data=data or {})
        with self._lock:
            subscribers = list(self._subscribers)
        dropped = 0
        for q in subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dropped += 1
        logger.info("events.publish", event_type=event, dropped=dropped)


broker = EventBroker()


def sse_stream(q: queue.Queue[EventMessage], *, keepalive_seconds: int = 15) -> Generator[bytes, None, None]:
    last_ping = time.time()
    try:
        while True:
            timeout = max(0.0, keepalive_seconds - (time.time() - last_ping))
            try:
                msg = q.get(timeout=timeout)
                payload = json.dumps(msg.data, separators=(",", ":"), default=str)
                yield f"event: {msg.event}\n".encode("utf-8")
                yield f"data: {payload}\n\n".encode("utf-8")
            except queue.Empty:
                last_ping = time.time()
                yield b": keep-alive\n\n"
    finally:
        broker.unsubscribe(q)
