from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine

from agent_observability import record_task, start_flow
from database import get_db
from models import (
    ObservabilityEvent,
    ObservedAgent,
    ObservedFlow,
    ObservedFlowAgent,
    ObservedTask,
)


@pytest.fixture
def observation_session(api: TestClient) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ObservedAgent.__table__,
        ObservedFlow.__table__,
        ObservedFlowAgent.__table__,
        ObservedTask.__table__,
        ObservabilityEvent.__table__,
    ):
        table.create(engine)
    session = Session(engine)

    def override() -> Iterator[Session]:
        yield session

    from main import app

    app.dependency_overrides[get_db] = override
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()


def seed_trace(session: Session, flow_id: str = "chat-1") -> list[ObservedTask]:
    start_flow(
        session,
        flow_id=flow_id,
        flow_type="chat_session",
        triggered_by="client_inbound_message:message-1",
        agent_ids=["first_line_cx"],
    )
    query = record_task(
        session,
        flow_id=flow_id,
        agent_id="first_line_cx",
        action_type="query",
        trigger="external:client_inbound_message:message-1",
        task_id=f"{flow_id}-query",
    )
    tool = record_task(
        session,
        flow_id=flow_id,
        agent_id="first_line_cx",
        action_type="tool_call",
        trigger=query.task_id,
        previous_task_id=query.task_id,
        task_id=f"{flow_id}-tool",
    )
    delivery = record_task(
        session,
        flow_id=flow_id,
        agent_id="first_line_cx",
        action_type="deliver",
        trigger=tool.task_id,
        previous_task_id=tool.task_id,
        task_id=f"{flow_id}-deliver",
    )
    return [query, tool, delivery]


def test_all_observability_routes_require_the_backoffice_jwt(
    api: TestClient, observation_session: Session
) -> None:
    for path in (
        "/observability/agents",
        "/observability/executions",
        "/observability/flows",
        "/observability/stream?max_events=1",
    ):
        assert api.get(path).status_code == 401


def test_agent_list_and_detail_include_trackflow_fields(
    signed_in: TestClient, observation_session: Session
) -> None:
    seed_trace(observation_session)
    listing = signed_in.get("/observability/agents")
    assert listing.status_code == 200
    assert {agent["agent_id"] for agent in listing.json()} == {
        "first_line_cx",
        "rfp_pipeline",
    }

    detail = signed_in.get("/observability/agents/first_line_cx")
    assert detail.status_code == 200
    body = detail.json()
    assert body["name"] == "First-line CX agent"
    assert body["flow_types"] == ["chat_session"]
    assert len(body["last_5_flows"]) == 1
    assert [task["action_type"] for task in body["last_10_tasks"]] == [
        "deliver",
        "tool_call",
        "query",
    ]
    assert "pause" in body["available_actions"]


def test_flow_detail_orders_tasks_and_keeps_participants_separate(
    signed_in: TestClient, observation_session: Session
) -> None:
    seed_trace(observation_session)
    response = signed_in.get("/observability/flows/chat-1")
    assert response.status_code == 200
    participant = response.json()["participating_agents"][0]
    assert participant["agent_id"] == "first_line_cx"
    assert [task["task_id"] for task in participant["tasks"]] == [
        "chat-1-query",
        "chat-1-tool",
        "chat-1-deliver",
    ]


def test_task_trace_reconstructs_trigger_previous_next_and_derived(
    signed_in: TestClient, observation_session: Session
) -> None:
    seed_trace(observation_session)
    response = signed_in.get("/observability/tasks/chat-1-tool")
    assert response.status_code == 200
    body = response.json()
    assert body["trigger"] == "chat-1-query"
    assert body["previous_task"]["task_id"] == "chat-1-query"
    assert body["next_task"]["task_id"] == "chat-1-deliver"
    assert [task["task_id"] for task in body["derived_tasks"]] == ["chat-1-deliver"]


def test_paginated_log_is_chronological_without_duplicates_or_skips(
    signed_in: TestClient, observation_session: Session
) -> None:
    seed_trace(observation_session, "chat-1")
    seed_trace(observation_session, "chat-2")
    page_one = signed_in.get("/observability/executions?page=1&page_size=4").json()
    page_two = signed_in.get("/observability/executions?page=2&page_size=4").json()
    ids_one = [task["task_id"] for task in page_one["items"]]
    ids_two = [task["task_id"] for task in page_two["items"]]
    assert page_one["total"] == 6
    assert len(ids_one) == 4
    assert len(ids_two) == 2
    assert set(ids_one).isdisjoint(ids_two)
    assert set(ids_one + ids_two) == {
        "chat-1-query",
        "chat-1-tool",
        "chat-1-deliver",
        "chat-2-query",
        "chat-2-tool",
        "chat-2-deliver",
    }


def test_sse_replays_persisted_event_with_required_name_and_shape(
    signed_in: TestClient, observation_session: Session
) -> None:
    seed_trace(observation_session)
    response = signed_in.get("/observability/stream?max_events=1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert "event: agent_status_changed" in response.text
    assert '"agent_id":"first_line_cx"' in response.text
    assert '"flow_id":"chat-1"' in response.text


def test_trackflow_intervention_rules_are_derived_automatically(
    signed_in: TestClient, observation_session: Session
) -> None:
    start_flow(
        observation_session,
        flow_id="chat-stuck",
        flow_type="chat_session",
        triggered_by="client_inbound_message:stuck",
        agent_ids=["first_line_cx"],
    )
    stuck = record_task(
        observation_session,
        flow_id="chat-stuck",
        agent_id="first_line_cx",
        action_type="tool_call",
        trigger="external:client_inbound_message:stuck",
    )
    stuck.created_at = datetime.now(UTC) - timedelta(seconds=21)
    observation_session.add(stuck)

    start_flow(
        observation_session,
        flow_id="rfp-loop",
        flow_type="rfp_workflow",
        triggered_by="rfp_ticket:loop",
        agent_ids=["rfp_pipeline"],
    )
    for iteration in range(4):
        record_task(
            observation_session,
            flow_id="rfp-loop",
            agent_id="rfp_pipeline",
            action_type="evaluate",
            trigger="rfp-loop",
            department_id="warehouse",
            payload={"overall_pass": False, "iteration": iteration + 1},
        )
    observation_session.commit()

    agents = {agent["agent_id"]: agent for agent in signed_in.get("/observability/agents").json()}
    assert agents["first_line_cx"]["needs_intervention"] is True
    assert agents["rfp_pipeline"]["needs_intervention"] is True
