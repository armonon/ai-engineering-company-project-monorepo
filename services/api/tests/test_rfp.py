from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from rfp_intake import IntakeResult, RfpClassification
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from database import get_db
from models import DepartmentSection, RfpMetadataRecord, RfpTicket, RfpTicketStatus
from routers.rfp import persist_intake_result


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
