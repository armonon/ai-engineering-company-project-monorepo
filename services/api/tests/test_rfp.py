from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from rfp_intake import IntakeResult, ResponseResult, RfpClassification, generate_response
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from database import get_db
from models import (
    DepartmentSection,
    FinalRfpDocument,
    RfpMetadataRecord,
    RfpTicket,
    RfpTicketStatus,
)
from routers.rfp import persist_intake_result, persist_response_result


@pytest.fixture
def rfp_session(signed_in: TestClient) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        RfpTicket.__table__,
        RfpMetadataRecord.__table__,
        DepartmentSection.__table__,
        FinalRfpDocument.__table__,
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


def test_upload_creates_analyzing_ticket_and_schedules_background_work(
    signed_in: TestClient,
    rfp_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("RFP_RAW_DIR", str(tmp_path / "raw"))
    calls: list[tuple[str, str]] = []
    with patch(
        "routers.rfp.process_ticket_background",
        side_effect=lambda ticket_id, path: calls.append((ticket_id, path)),
    ):
        response = signed_in.post(
            "/rfp/tickets",
            files={"document": ("client.pdf", b"%PDF-1.4 fixture", "application/pdf")},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "analyzing"
    ticket = rfp_session.get(RfpTicket, payload["ticket_id"])
    assert ticket is not None
    assert ticket.status == RfpTicketStatus.ANALYZING
    assert Path(ticket.raw_pdf_path).read_bytes().startswith(b"%PDF")
    assert calls == [(payload["ticket_id"], ticket.raw_pdf_path)]


def test_upload_rejects_non_pdf_without_creating_ticket(
    signed_in: TestClient, rfp_session: Session
):
    response = signed_in.post(
        "/rfp/tickets",
        files={"document": ("pitch.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert rfp_session.exec(select(RfpTicket)).all() == []


def test_persist_valid_intake_handoff_and_sections(rfp_session: Session):
    ticket = RfpTicket(
        ticket_id="ticket-1",
        status=RfpTicketStatus.ANALYZING,
        raw_pdf_path="/tmp/ticket-1.pdf",
        created_by="1",
    )
    rfp_session.add(ticket)
    rfp_session.commit()
    metadata = {
        "rfp_id": "MV-LOG-2026-03",
        "client_name": "ModaViva, S.L.",
        "client_country": "Spain",
        "currency": "EUR",
        "services_requested": ["warehousing", "reverse_logistics"],
        "monthly_volume": None,
        "deadline": "August 28, 2026",
        "budget_range": None,
        "departments_needed": ["warehouse", "reverse"],
        "readability_metrics": {"estimated_tokens": 351},
    }
    sections = [
        {
            "department_id": "warehouse",
            "contact": "Ana Whitfield",
            "key_aspects": ["Confirm monthly volume."],
        },
        {
            "department_id": "reverse",
            "contact": "Sofía Ramos",
            "key_aspects": ["Returns processing requested."],
        },
    ]
    result = IntakeResult(
        ticket_id="ticket-1",
        status="intake_complete",
        classification=RfpClassification(True, "client_requests_trackflow_services"),
        metadata=metadata,
        sections=sections,
        sales_summary="Coordinate warehouse and reverse.",
        handoff_payload={
            "ticket_id": "ticket-1",
            "metadata": metadata,
            "workstreams": sections,
        },
        markdown_path="/tmp/ticket-1.md",
    )

    persist_intake_result(rfp_session, result)

    saved = rfp_session.get(RfpTicket, "ticket-1")
    assert saved is not None
    assert saved.status == RfpTicketStatus.INTAKE_COMPLETE
    assert saved.ready_for_generation is True
    assert saved.handoff_payload["ticket_id"] == "ticket-1"
    assert len(rfp_session.exec(select(DepartmentSection)).all()) == 2
    assert rfp_session.exec(select(RfpMetadataRecord)).one().currency == "EUR"


def test_discarded_document_never_creates_metadata_or_handoff(rfp_session: Session):
    rfp_session.add(
        RfpTicket(
            ticket_id="bad-ticket",
            status=RfpTicketStatus.ANALYZING,
            raw_pdf_path="/tmp/bad.pdf",
            created_by="1",
        )
    )
    rfp_session.commit()
    persist_intake_result(
        rfp_session,
        IntakeResult(
            ticket_id="bad-ticket",
            status="discarded",
            classification=RfpClassification(False, "supplier_pitch_not_client_rfp"),
            metadata={},
            sections=[],
            sales_summary="",
            handoff_payload={},
            markdown_path="/tmp/bad.md",
        ),
    )
    saved = rfp_session.get(RfpTicket, "bad-ticket")
    assert saved is not None
    assert saved.status == RfpTicketStatus.DISCARDED
    assert saved.ready_for_generation is False
    assert rfp_session.exec(select(RfpMetadataRecord)).all() == []


def _ready_ticket(session: Session, ticket_id: str = "ready-ticket") -> RfpTicket:
    metadata = {
        "client_name": "ModaViva",
        "client_country": "Spain",
        "currency": "EUR",
        "monthly_volume": 5_000,
    }
    workstreams = [
        {
            "department_id": "warehouse",
            "contact": "Ana Whitfield",
            "key_aspects": ["Confirm capacity."],
        }
    ]
    ticket = RfpTicket(
        ticket_id=ticket_id,
        status=RfpTicketStatus.INTAKE_COMPLETE,
        raw_pdf_path="/tmp/ready.pdf",
        created_by="1",
        ready_for_generation=True,
        handoff_payload={
            "ticket_id": ticket_id,
            "metadata": metadata,
            "workstreams": workstreams,
        },
    )
    session.add(ticket)
    session.add(
        DepartmentSection(
            ticket_id=ticket_id,
            department_id="warehouse",
            contact="Ana Whitfield",
            key_aspects=["Confirm capacity."],
        )
    )
    session.commit()
    return ticket


def test_generation_endpoint_consumes_the_persisted_handoff(
    signed_in: TestClient, rfp_session: Session
) -> None:
    ticket = _ready_ticket(rfp_session)
    calls: list[tuple[str, dict]] = []
    with patch(
        "routers.rfp.generate_ticket_background",
        side_effect=lambda ticket_id, handoff: calls.append((ticket_id, handoff)),
    ):
        response = signed_in.post(f"/rfp/tickets/{ticket.ticket_id}/generate")

    assert response.status_code == 202
    assert response.json()["status"] == "drafting"
    assert calls == [(ticket.ticket_id, ticket.handoff_payload)]
    rfp_session.refresh(ticket)
    assert ticket.status == RfpTicketStatus.DRAFTING


def test_generation_requires_an_intake_complete_ticket(
    signed_in: TestClient, rfp_session: Session
) -> None:
    ticket = RfpTicket(
        ticket_id="still-analyzing",
        status=RfpTicketStatus.ANALYZING,
        raw_pdf_path="/tmp/pending.pdf",
        created_by="1",
    )
    rfp_session.add(ticket)
    rfp_session.commit()
    response = signed_in.post(f"/rfp/tickets/{ticket.ticket_id}/generate")
    assert response.status_code == 409


def test_response_result_persists_draft_evaluation_and_part3_handoff(
    rfp_session: Session,
) -> None:
    ticket = _ready_ticket(rfp_session, "generated-ticket")
    evaluation = {
        "department_id": "warehouse",
        "readability": {"pass": True, "score": 10, "details": {}},
        "relevance": {"pass": True, "missing_aspects": []},
        "compliance": {"pass": True, "rule_ids": [], "violations": []},
        "overall_pass": True,
        "feedback_for_generator": "",
    }
    section = {
        "department_id": "warehouse",
        "contact": "Ana Whitfield",
        "key_aspects": ["Confirm capacity."],
        "draft_content": "Approved warehouse draft.",
        "evaluation_result": evaluation,
        "iteration": 1,
        "complete": True,
        "needs_human_review": False,
    }
    handoff = {
        "ticket_id": ticket.ticket_id,
        "metadata": ticket.handoff_payload["metadata"],
        "sections": [section],
    }
    persist_response_result(
        rfp_session,
        ResponseResult(
            ticket_id=ticket.ticket_id,
            status="under_evaluation",
            sections=[section],
            handoff_payload=handoff,
        ),
    )

    saved_ticket = rfp_session.get(RfpTicket, ticket.ticket_id)
    saved_section = rfp_session.exec(
        select(DepartmentSection).where(DepartmentSection.ticket_id == ticket.ticket_id)
    ).one()
    assert saved_ticket is not None
    assert saved_ticket.status == RfpTicketStatus.UNDER_EVALUATION
    assert saved_ticket.ready_for_generation is False
    assert saved_ticket.handoff_payload["sections"][0]["draft_content"] == section["draft_content"]
    assert saved_section.draft_content == section["draft_content"]
    assert saved_section.evaluation_results == evaluation
    assert saved_section.approval_status == "ready_for_approval"


def _approval_ready_ticket(session: Session) -> RfpTicket:
    ticket = _ready_ticket(session, "approval-ticket")
    result = generate_response(ticket.handoff_payload)
    persist_response_result(session, result)
    session.refresh(ticket)
    return ticket


def test_approval_branches_resume_independently_and_create_final_document(
    signed_in: TestClient,
    rfp_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket = _approval_ready_ticket(rfp_session)
    monkeypatch.setenv("RFP_CHECKPOINT_DB", str(tmp_path / "approval-checkpoints.sqlite3"))

    started = signed_in.post(f"/rfp/tickets/{ticket.ticket_id}/approval/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "waiting_for_approval"
    assert started.json()["departments"] == {"warehouse": "waiting_for_approval"}

    approved = signed_in.post(
        f"/rfp/tickets/{ticket.ticket_id}/approval/warehouse",
        json={"decision": "approve", "reason": "Capacity confirmed."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "done"
    assert approved.json()["approval_status"] == "approved"

    document = signed_in.get(f"/rfp/tickets/{ticket.ticket_id}/final-document")
    assert document.status_code == 200
    assert "Approved by Ana Whitfield" in document.json()["content"]
    assert rfp_session.exec(select(FinalRfpDocument)).one().currency == "EUR"
