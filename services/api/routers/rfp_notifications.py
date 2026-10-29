"""Process-local fan-out and short replay for TrackFlow RFP notifications."""

from __future__ import annotations

import queue
import threading
from collections import deque
from contextlib import contextmanager
from typing import Any, Iterator


class RfpNotificationBroker:
    """One event producer, independent queues for every connected dashboard."""

    def __init__(self, replay_size: int = 100) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=replay_size)
        self._subscribers: set[queue.Queue[dict[str, Any]]] = set()
        self._next_id = 1
        self._lock = threading.Lock()

    def publish(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            event = {
                "id": self._next_id,
                "event": "rfp_ticket_created",
                "data": data,
            }
            self._next_id += 1
            self._events.append(event)
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            subscriber.put_nowait(event)
        return event

    def replay_after(self, event_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return [event for event in self._events if int(event["id"]) > event_id]

    @contextmanager
    def subscribe(self) -> Iterator[queue.Queue[dict[str, Any]]]:
        subscriber: queue.Queue[dict[str, Any]] = queue.Queue()
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._events.clear()
            self._subscribers.clear()
            self._next_id = 1


rfp_notification_broker = RfpNotificationBroker()
