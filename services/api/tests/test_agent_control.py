from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from agent_control import InvalidControlTransition, apply_control
from agent_observability import record_task, start_flow
from models import (
    ObservabilityEvent,
    ObservedAgent,
    ObservedFlow,
    ObservedFlowAgent,
    ObservedTask,
    RfpTicket,
    RfpTicketStatus,
)


@pytest.fixture
def control_session(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        RfpTicket.__table__,
        ObservedAgent.__table__,
        ObservedFlow.__table__,
        ObservedFlowAgent.__table__,
        ObservedTask.__table__,
        ObservabilityEvent.__table__,
    ):
        table.create(engine)
    monkeypatch.setattr("routers.control.inventory_engine", lambda: engine)
    with Session(engine) as session:
        yield session


def seed_execution(
    session: Session,
    *,
    agent_id: str = "first_line_cx",
    flow_id: str = "chat-control",
) -> ObservedTask:
    start_flow(
        session,
        flow_id=flow_id,
        flow_type="chat_session" if agent_id == "first_line_cx" else "rfp_workflow",
        triggered_by="external:test",
        agent_ids=[agent_id],
    )
    return record_task(
        session,
        flow_id=flow_id,
        agent_id=agent_id,
        action_type="query",
        trigger="external:test",
        task_id=f"{flow_id}-query",
    )


def test_pause_persists_checkpoint_and_audits_actor(control_session: Session) -> None:
    first = seed_execution(control_session)
    event = apply_control(
        control_session,
        agent_id="first_line_cx",
        flow_id="chat-control",
        action="pause",
        actor_id="user_7",
    )
    participation = control_session.exec(select(ObservedFlowAgent)).one()
    audit = control_session.get(ObservedTask, event["task_id"])
    assert participation.status == "paused"
    assert participation.checkpoint_data["last_task_id"] == first.task_id
    assert participation.checkpoint_data["chat_hold_open"] is True
    assert audit is not None
    assert audit.action_type == "pause"
    assert audit.actor_id == "user_7"
    assert audit.created_at is not None


def test_resume_uses_the_same_checkpoint_without_restarting(control_session: Session) -> None:
    seed_execution(control_session)
    apply_control(
        control_session,
        agent_id="first_line_cx",
        flow_id="chat-control",
        action="pause",
        actor_id="user_1",
    )
    participation = control_session.exec(select(ObservedFlowAgent)).one()
    checkpoint = dict(participation.checkpoint_data)
    apply_control(
        control_session,
        agent_id="first_line_cx",
        flow_id="chat-control",
        action="resume",
        actor_id="user_1",
    )
    control_session.refresh(participation)
    tasks = control_session.exec(
        select(ObservedTask).order_by(ObservedTask.created_at, ObservedTask.task_id)
    ).all()
    assert participation.status == "running"
    assert participation.checkpoint_data == checkpoint
    assert [task.action_type for task in tasks] == ["query", "pause", "resume"]


def test_cancel_is_terminal_and_cancels_pending_children(control_session: Session) -> None:
    seed_execution(control_session, agent_id="rfp_pipeline", flow_id="rfp-ticket-1")
    pending = record_task(
        control_session,
        flow_id="rfp-ticket-1",
        agent_id="rfp_pipeline",
        action_type="write",
        trigger="rfp-ticket-1-query",
        previous_task_id="rfp-ticket-1-query",
        department_id="warehouse",
    )
    pending.status = "pending"
    control_session.add(pending)
    control_session.commit()
    apply_control(
        control_session,
        agent_id="rfp_pipeline",
        flow_id="rfp-ticket-1",
        action="cancel",
        actor_id="user_2",
    )
    control_session.refresh(pending)
    flow = control_session.get(ObservedFlow, "rfp-ticket-1")
    assert pending.status == "cancelled"
    assert flow is not None and flow.status == "cancelled"
    with pytest.raises(InvalidControlTransition, match="Cannot resume"):
        apply_control(
            control_session,
            agent_id="rfp_pipeline",
            flow_id="rfp-ticket-1",
            action="resume",
            actor_id="user_2",
        )


def test_rfp_pause_reuses_existing_langgraph_checkpoint_ids(control_session: Session) -> None:
    control_session.add(
        RfpTicket(
            ticket_id="ticket-2",
            status=RfpTicketStatus.WAITING_FOR_APPROVAL,
            raw_pdf_path="/tmp/ticket-2.pdf",
            created_by="1",
            handoff_payload={
                "approval_states": {
                    "warehouse": {"thread_id": "rfp-ticket-2:warehouse"},
                    "reverse": {"thread_id": "rfp-ticket-2:reverse"},
                }
            },
        )
    )
    control_session.commit()
    seed_execution(control_session, agent_id="rfp_pipeline", flow_id="rfp-ticket-2")
    apply_control(
        control_session,
        agent_id="rfp_pipeline",
        flow_id="rfp-ticket-2",
        action="pause",
        actor_id="user_3",
    )
    participation = control_session.exec(
        select(ObservedFlowAgent).where(ObservedFlowAgent.flow_id == "rfp-ticket-2")
    ).one()
    assert participation.checkpoint_data["langgraph_thread_ids"] == [
        "rfp-ticket-2:warehouse",
        "rfp-ticket-2:reverse",
    ]


def _authenticate_and_subscribe(websocket, token: str) -> dict:
    websocket.send_json({"command": "authenticate", "data": {"token": token}})
    assert websocket.receive_json()["event"] == "authenticated"
    websocket.send_json(
        {
            "command": "subscribe",
            "data": {"agent_id": "first_line_cx", "flow_id": "chat-control"},
        }
    )
    state = websocket.receive_json()
    assert state["event"] == "control_state"
    return state["data"]


def test_websocket_pubsub_auth_and_state_recovery(
    signed_in: TestClient, control_session: Session
) -> None:
    seed_execution(control_session)
    token = signed_in.headers["Authorization"].removeprefix("Bearer ")
    with signed_in.websocket_connect("/observability/control") as first:
        with signed_in.websocket_connect("/observability/control") as second:
            _authenticate_and_subscribe(first, token)
            _authenticate_and_subscribe(second, token)
            first.send_json(
                {
                    "command": "pause",
                    "data": {"agent_id": "first_line_cx", "flow_id": "chat-control"},
                }
            )
            first_event = first.receive_json()
            second_event = second.receive_json()
            assert first_event["event"] == "control_applied"
            assert second_event["event"] == "control_applied"
            assert first_event["data"]["status"] == "paused"
            assert first_event["data"]["actor_id"] == "user_1"

    with signed_in.websocket_connect("/observability/control") as recovered:
        recovered_state = _authenticate_and_subscribe(recovered, token)
        assert recovered_state["agent_status"] == "paused"
        assert recovered_state["checkpoint"]["last_task_id"] == "chat-control-query"


def test_websocket_rejects_invalid_transition(
    signed_in: TestClient, control_session: Session
) -> None:
    seed_execution(control_session)
    token = signed_in.headers["Authorization"].removeprefix("Bearer ")
    with signed_in.websocket_connect("/observability/control") as websocket:
        _authenticate_and_subscribe(websocket, token)
        websocket.send_json(
            {
                "command": "resume",
                "data": {"agent_id": "first_line_cx", "flow_id": "chat-control"},
            }
        )
        error = websocket.receive_json()
        assert error["event"] == "control_error"
        assert "Cannot resume" in error["data"]["message"]
