from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _token(client: TestClient) -> str:
    return client.headers["Authorization"].removeprefix("Bearer ")


def _receive_until(websocket, event_name: str, limit: int = 100) -> list[dict]:
    received: list[dict] = []
    for _ in range(limit):
        message = websocket.receive_json()
        received.append(message)
        if message["event"] == event_name:
            return received
    raise AssertionError(f"Did not receive {event_name!r}")


def test_chat_websocket_rejects_missing_jwt(api: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as disconnected:
        with api.websocket_connect("/agent/chat/chat-unauthorized") as socket:
            socket.receive_json()
    assert disconnected.value.code == 4401


def test_chat_streams_named_token_events_and_rehydrates_session(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHAT_TOKEN_DELAY_SECONDS", "0")
    token = _token(signed_in)
    answer = "Your TrackFlow return is ready for review."

    fake_runtime = SimpleNamespace(
        invoke=lambda *_args: SimpleNamespace(answer=answer)
    )
    with patch("routers.chat.runtime", fake_runtime):
        with signed_in.websocket_connect(f"/agent/chat/chat-stream?token={token}") as socket:
            snapshot = socket.receive_json()
            assert snapshot["event"] == "session_snapshot"
            assert snapshot["data"]["agent_id"] == "first_line_cx"
            assert snapshot["data"]["messages"] == []

            socket.send_json(
                {
                    "event": "user_message",
                    "data": {"session_id": "chat-stream", "text": "Check my return"},
                }
            )
            events = _receive_until(socket, "generation_completed")

    chunks = [event for event in events if event["event"] == "token_chunk"]
    assert "".join(event["data"]["token"] for event in chunks) == answer
    assert [event["data"]["sequence"] for event in chunks] == list(
        range(1, len(chunks) + 1)
    )

    with signed_in.websocket_connect(f"/agent/chat/chat-stream?token={token}") as recovered:
        snapshot = recovered.receive_json()
    assert snapshot["event"] == "session_snapshot"
    assert [message["role"] for message in snapshot["data"]["messages"]] == [
        "user",
        "assistant",
    ]
    assert snapshot["data"]["messages"][1]["text"] == answer
    assert snapshot["data"]["messages"][1]["status"] == "completed"


def test_interrupt_aborts_original_stream_and_starts_a_new_turn(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHAT_TOKEN_DELAY_SECONDS", "0.01")
    token = _token(signed_in)

    def answer(question: str, *_args) -> SimpleNamespace:
        if "return" in question:
            return SimpleNamespace(answer="I can help redirect this conversation to returns.")
        return SimpleNamespace(answer=" ".join(f"tracking-{index}" for index in range(30)))

    with patch("routers.chat.runtime", SimpleNamespace(invoke=answer)):
        with signed_in.websocket_connect(f"/agent/chat/chat-interrupt?token={token}") as socket:
            assert socket.receive_json()["event"] == "session_snapshot"
            socket.send_json(
                {
                    "event": "user_message",
                    "data": {"session_id": "chat-interrupt", "text": "Track my parcel"},
                }
            )
            first_events = _receive_until(socket, "token_chunk")
            old_chunk = next(event for event in first_events if event["event"] == "token_chunk")
            old_message_id = old_chunk["data"]["message_id"]

            socket.send_json(
                {
                    "event": "interrupt_requested",
                    "data": {
                        "session_id": "chat-interrupt",
                        "new_input": "Wait, I want to make a return",
                    },
                }
            )
            redirected = _receive_until(socket, "generation_completed", limit=150)

    interrupted_index = next(
        index
        for index, event in enumerate(redirected)
        if event["event"] == "generation_interrupted"
    )
    assert redirected[interrupted_index]["data"] == {
        "session_id": "chat-interrupt",
        "message_id": old_message_id,
        "status": "interrupted",
    }
    assert not any(
        event["event"] == "token_chunk"
        and event["data"]["message_id"] == old_message_id
        for event in redirected[interrupted_index + 1 :]
    )
    new_user = next(event for event in redirected if event["event"] == "user_message")
    assert "return" in new_user["data"]["text"].lower()

    with signed_in.websocket_connect(f"/agent/chat/chat-interrupt?token={token}") as recovered:
        snapshot = recovered.receive_json()["data"]
    assistants = [
        message for message in snapshot["messages"] if message["role"] == "assistant"
    ]
    assert len(assistants) == 2
    assert assistants[0]["status"] == "interrupted"
    assert assistants[0]["text"]
    assert assistants[1]["status"] == "completed"
    assert "returns" in assistants[1]["text"]
