"""JWT-authenticated WebSocket pub/sub for agent operational controls."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlmodel import Session

from agent_control import InvalidControlTransition, apply_control, control_state
from database import inventory_engine, users_table
from security import decode_token

router = APIRouter(tags=["agent-control"])


class ControlHub:
    def __init__(self) -> None:
        self._subscriptions: dict[tuple[str, str], set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, websocket: WebSocket, agent_id: str, flow_id: str) -> None:
        async with self._lock:
            self._subscriptions[(agent_id, flow_id)].add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            for subscribers in self._subscriptions.values():
                subscribers.discard(websocket)

    async def broadcast(self, agent_id: str, flow_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = tuple(self._subscriptions[(agent_id, flow_id)])
        dead: list[WebSocket] = []
        for subscriber in subscribers:
            try:
                await subscriber.send_json(message)
            except (RuntimeError, WebSocketDisconnect):
                dead.append(subscriber)
        for subscriber in dead:
            await self.disconnect(subscriber)


hub = ControlHub()


def _authenticate(token: str) -> str:
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid or expired backoffice token") from exc
    user = users_table().get(doc_id=user_id)
    if user is None or not user.get("is_active", True):
        raise ValueError("Backoffice account is unavailable")
    return f"user_{user_id}"


@router.websocket("/observability/control")
async def agent_control_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    subscribed: tuple[str, str] | None = None
    try:
        try:
            auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            if auth_message.get("command") != "authenticate":
                raise ValueError("Authenticate before sending control commands")
            actor_id = _authenticate(str(auth_message.get("data", {}).get("token", "")))
        except (TimeoutError, ValueError) as exc:
            await websocket.send_json(
                {"event": "control_error", "data": {"message": str(exc)}}
            )
            await websocket.close(code=4401)
            return
        await websocket.send_json(
            {"event": "authenticated", "data": {"actor_id": actor_id}}
        )

        while True:
            message = await websocket.receive_json()
            command = str(message.get("command", ""))
            data = message.get("data") or {}
            agent_id = str(data.get("agent_id", ""))
            flow_id = str(data.get("flow_id", ""))
            try:
                # A fresh session prevents a long-lived socket from serving stale
                # identity-map state after another operator changes this execution.
                with Session(inventory_engine()) as session:
                    if command == "subscribe":
                        state = control_state(session, agent_id, flow_id)
                        await hub.subscribe(websocket, agent_id, flow_id)
                        subscribed = (agent_id, flow_id)
                        await websocket.send_json({"event": "control_state", "data": state})
                        continue
                    if command not in {"pause", "resume", "cancel"}:
                        raise InvalidControlTransition(
                            "command must be subscribe, pause, resume, or cancel"
                        )
                    if subscribed != (agent_id, flow_id):
                        raise InvalidControlTransition(
                            "Subscribe to this agent execution before controlling it"
                        )
                    event = apply_control(
                        session,
                        agent_id=agent_id,
                        flow_id=flow_id,
                        action=command,  # type: ignore[arg-type]
                        actor_id=actor_id,
                    )
                await hub.broadcast(
                    agent_id,
                    flow_id,
                    {"event": "control_applied", "data": event},
                )
            except (InvalidControlTransition, LookupError) as exc:
                await websocket.send_json(
                    {
                        "event": "control_error",
                        "data": {
                            "agent_id": agent_id,
                            "flow_id": flow_id,
                            "command": command,
                            "message": str(exc),
                        },
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(websocket)
