"""JWT-authenticated, resumable WebSocket channel for the First-line CX agent."""

from __future__ import annotations

import asyncio
import os
import re
from collections import defaultdict
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from routers.agent import runtime
from security import authenticate_websocket_user

router = APIRouter(tags=["first-line-cx-chat"])


class ChatMessage(TypedDict):
    message_id: str
    role: Literal["user", "assistant"]
    text: str
    status: Literal["completed", "streaming", "interrupted"]
    created_at: str


class ChatSession(TypedDict):
    session_id: str
    agent_id: Literal["first_line_cx"]
    user_id: str
    client_id: str
    status: Literal["active", "interrupted", "closed"]
    created_at: str
    messages: list[ChatMessage]


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ChatSessionStore:
    """Single-process conversation checkpoint used for reconnect snapshots."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}

    def open(self, session_id: str, user_id: str) -> ChatSession:
        existing = self._sessions.get(session_id)
        if existing is not None:
            if existing["user_id"] != user_id:
                raise PermissionError("Chat session belongs to another user")
            return existing
        session: ChatSession = {
            "session_id": session_id,
            "agent_id": "first_line_cx",
            "user_id": user_id,
            "client_id": f"client_{user_id}",
            "status": "active",
            "created_at": _now(),
            "messages": [],
        }
        self._sessions[session_id] = session
        return session

    def snapshot(self, session_id: str) -> dict[str, Any]:
        session = self._sessions[session_id]
        return {
            "session_id": session["session_id"],
            "agent_id": session["agent_id"],
            "user_id": session["user_id"],
            "client_id": session["client_id"],
            "status": session["status"],
            "created_at": session["created_at"],
            "messages": [dict(message) for message in session["messages"]],
        }

    def add_message(
        self,
        session_id: str,
        role: Literal["user", "assistant"],
        text: str,
        status: Literal["completed", "streaming", "interrupted"],
    ) -> ChatMessage:
        message: ChatMessage = {
            "message_id": f"msg_{uuid4().hex}",
            "role": role,
            "text": text,
            "status": status,
            "created_at": _now(),
        }
        self._sessions[session_id]["messages"].append(message)
        return message

    def reset_for_tests(self) -> None:
        self._sessions.clear()


class ChatHub:
    """Per-session pub/sub: one producer can serve any number of viewers."""

    def __init__(self, store: ChatSessionStore) -> None:
        self.store = store
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._running: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        subscriber: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers[session_id].add(subscriber)
        return subscriber

    async def disconnect(
        self, session_id: str, subscriber: asyncio.Queue[dict[str, Any]]
    ) -> None:
        async with self._lock:
            self._subscribers[session_id].discard(subscriber)

    async def publish(self, session_id: str, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, "data": data}
        async with self._lock:
            subscribers = tuple(self._subscribers[session_id])
        for subscriber in subscribers:
            subscriber.put_nowait(payload)

    async def start_generation(self, session_id: str, text: str, principal: str) -> None:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            raise ValueError("Message must contain visible text")
        if len(cleaned) > 500:
            raise ValueError("Message must be 500 characters or fewer")
        async with self._lock:
            active = self._running.get(session_id)
            if active and not active.done():
                raise ValueError("Interrupt the active response before sending a new message")
            user_message = self.store.add_message(
                session_id, "user", cleaned, "completed"
            )
            assistant = self.store.add_message(session_id, "assistant", "", "streaming")
            self.store._sessions[session_id]["status"] = "active"
            task = asyncio.create_task(
                self._produce(session_id, cleaned, principal, assistant),
                name=f"first-line-cx:{session_id}:{assistant['message_id']}",
            )
            self._running[session_id] = task
        await self.publish(session_id, "user_message", {
            "session_id": session_id,
            "message_id": user_message["message_id"],
            "text": cleaned,
        })

    async def _produce(
        self,
        session_id: str,
        text: str,
        principal: str,
        assistant: ChatMessage,
    ) -> None:
        try:
            run_id = f"{session_id}-{assistant['message_id']}"
            result = await asyncio.to_thread(
                runtime.invoke,
                text,
                run_id,
                principal,
            )
            # The secured graph validates the complete answer before release.
            # Transport chunks then flow independently and remain cancellable.
            chunks = re.findall(r"\S+\s*", result.answer) or [result.answer]
            delay = max(float(os.getenv("CHAT_TOKEN_DELAY_SECONDS", "0.025")), 0.0)
            for sequence, token in enumerate(chunks, start=1):
                await asyncio.sleep(delay)
                assistant["text"] += token
                await self.publish(
                    session_id,
                    "token_chunk",
                    {
                        "session_id": session_id,
                        "message_id": assistant["message_id"],
                        "token": token,
                        "sequence": sequence,
                    },
                )
            assistant["status"] = "completed"
            self.store._sessions[session_id]["status"] = "active"
            await self.publish(
                session_id,
                "generation_completed",
                {
                    "session_id": session_id,
                    "message_id": assistant["message_id"],
                },
            )
        except asyncio.CancelledError:
            assistant["status"] = "interrupted"
            self.store._sessions[session_id]["status"] = "interrupted"
            await self.publish(
                session_id,
                "generation_interrupted",
                {
                    "session_id": session_id,
                    "message_id": assistant["message_id"],
                    "status": "interrupted",
                },
            )
            raise
        except Exception:
            assistant["status"] = "interrupted"
            self.store._sessions[session_id]["status"] = "interrupted"
            await self.publish(
                session_id,
                "chat_error",
                {
                    "session_id": session_id,
                    "message": "The First-line CX agent is temporarily unavailable.",
                },
            )
        finally:
            async with self._lock:
                if self._running.get(session_id) is asyncio.current_task():
                    self._running.pop(session_id, None)

    async def interrupt(self, session_id: str, new_input: str, principal: str) -> None:
        async with self._lock:
            task = self._running.get(session_id)
        if task is None or task.done():
            raise ValueError("There is no active generation to interrupt")
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await self.start_generation(session_id, new_input, principal)

    async def reset_for_tests(self) -> None:
        async with self._lock:
            tasks = tuple(self._running.values())
            self._running.clear()
            self._subscribers.clear()
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self.store.reset_for_tests()


chat_sessions = ChatSessionStore()
chat_hub = ChatHub(chat_sessions)


async def _send_events(
    websocket: WebSocket, subscriber: asyncio.Queue[dict[str, Any]]
) -> None:
    while True:
        await websocket.send_json(await subscriber.get())


@router.websocket("/agent/chat/{session_id}")
async def first_line_cx_chat(websocket: WebSocket, session_id: str) -> None:
    token = websocket.query_params.get("token", "")
    try:
        caller = authenticate_websocket_user(token)
        principal = f"{caller.role.value}:{caller.id}"
        chat_sessions.open(session_id, str(caller.id))
    except ValueError:
        await websocket.accept()
        await websocket.close(code=4401)
        return
    except PermissionError:
        await websocket.accept()
        await websocket.close(code=4403)
        return

    await websocket.accept()
    subscriber = await chat_hub.subscribe(session_id)
    sender = asyncio.create_task(_send_events(websocket, subscriber))
    await websocket.send_json(
        {"event": "session_snapshot", "data": chat_sessions.snapshot(session_id)}
    )
    try:
        while True:
            message = await websocket.receive_json()
            event = str(message.get("event", ""))
            data = message.get("data") or {}
            if str(data.get("session_id", "")) != session_id:
                raise ValueError("Event session_id must match the WebSocket session")
            if event == "user_message":
                await chat_hub.start_generation(session_id, str(data.get("text", "")), principal)
            elif event == "interrupt_requested":
                await chat_hub.interrupt(
                    session_id,
                    str(data.get("new_input", "")),
                    principal,
                )
            else:
                raise ValueError("Event must be user_message or interrupt_requested")
    except ValueError as exc:
        await websocket.send_json(
            {"event": "chat_error", "data": {"session_id": session_id, "message": str(exc)}}
        )
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with suppress(asyncio.CancelledError):
            await sender
        await chat_hub.disconnect(session_id, subscriber)
