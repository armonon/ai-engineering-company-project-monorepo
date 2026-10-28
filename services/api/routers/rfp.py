"""Existing-API boundary for the asynchronous TrackFlow RFP workflow."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from rfp_intake import IntakeResult, ResponseResult, build_response_graph, process_rfp
from sqlmodel import Session, select

from database import get_db, inventory_engine
from models import (
    DepartmentSection,
    RfpMetadataRecord,
    RfpTicket,
    RfpTicketStatus,
    UserInDB,
)
from security import get_current_user

logger = logging.getLogger("trackflow.rfp")
router = APIRouter(prefix="/rfp/tickets", tags=["rfp-workflow"])
MAX_PDF_BYTES = 12 * 1024 * 1024


def _raw_dir() -> Path:
    default = Path(__file__).resolve().parents[3] / "data" / "raw"
    return Path(os.getenv("RFP_RAW_DIR", default))


def _can_read(ticket: RfpTicket, caller: UserInDB) -> bool:
    return caller.role.value in {"admin", "manager"} or ticket.created_by == str(caller.id)


def _ticket_payload(session: Session, ticket: RfpTicket) -> dict[str, Any]:
    metadata = session.exec(
        select(RfpMetadataRecord).where(RfpMetadataRecord.ticket_id == ticket.ticket_id)
    ).first()
    sections = session.exec(
        select(DepartmentSection)
        .where(DepartmentSection.ticket_id == ticket.ticket_id)
        .order_by(DepartmentSection.department_id)
    ).all()
    return {
        "ticket_id": ticket.ticket_id,
        "rfp_id": ticket.rfp_id,
        "status": ticket.status.value,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "processing_error": ticket.processing_error,
        "sales_summary": ticket.sales_summary,
        "ready_for_generation": ticket.ready_for_generation,
        "metadata": (
            {
                "client_name": metadata.client_name,
                "client_country": metadata.client_country,
                "currency": metadata.currency,
                "services_requested": metadata.services_requested,
                "monthly_volume": metadata.monthly_volume,
                "deadline": metadata.deadline,
                "budget_range": metadata.budget_range,
                "departments_needed": metadata.departments_needed,
                "readability_metrics": metadata.readability_metrics,
            }
            if metadata
            else None
        ),
        "sections": [
            {
                "department_id": section.department_id,
                "contact": section.contact,
                "key_aspects": section.key_aspects,
                "draft_content": section.draft_content,
                "evaluation_result": section.evaluation_results,
                "approval_status": section.approval_status,
            }
            for section in sections
        ],
    }


def persist_intake_result(session: Session, result: IntakeResult) -> None:
    """Atomically persist graph output to the existing PostgreSQL stack."""
    ticket = session.get(RfpTicket, result.ticket_id)
    if ticket is None:
        raise LookupError("RFP ticket disappeared during processing")
    now = datetime.now(UTC)
    ticket.status = RfpTicketStatus(result.status)
    ticket.updated_at = now
    ticket.sales_summary = result.sales_summary or result.classification.reason
    if not result.classification.valid:
        ticket.ready_for_generation = False
        session.add(ticket)
        session.commit()
        return

    metadata = result.metadata
    ticket.rfp_id = metadata.get("rfp_id")
    ticket.handoff_payload = result.handoff_payload
    ticket.ready_for_generation = True
    session.add(ticket)
    session.add(
        RfpMetadataRecord(
            ticket_id=result.ticket_id,
            client_name=metadata["client_name"],
            client_country=metadata["client_country"],
            currency=metadata["currency"],
            services_requested=metadata["services_requested"],
            monthly_volume=metadata.get("monthly_volume"),
            deadline=metadata.get("deadline"),
            budget_range=metadata.get("budget_range"),
            departments_needed=metadata["departments_needed"],
            readability_metrics=metadata["readability_metrics"],
            markdown_path=result.markdown_path,
        )
    )
    for section in result.sections:
        session.add(
            DepartmentSection(
                ticket_id=result.ticket_id,
                department_id=section["department_id"],
                key_aspects=section["key_aspects"],
                contact=section["contact"],
            )
        )
    session.commit()


def process_ticket_background(ticket_id: str, raw_pdf_path: str) -> None:
    """Background boundary: graph runs outside the upload request/session."""
    try:
        result = process_rfp(raw_pdf_path, ticket_id)
        with Session(inventory_engine()) as session:
            persist_intake_result(session, result)
    except Exception:
        logger.exception("RFP intake failed for ticket %s", ticket_id)
        try:
            with Session(inventory_engine()) as session:
                ticket = session.get(RfpTicket, ticket_id)
                if ticket:
                    ticket.processing_error = "Intake processing failed; retry required."
                    ticket.updated_at = datetime.now(UTC)
                    session.add(ticket)
                    session.commit()
        except Exception:
            logger.exception("Could not persist RFP failure state for %s", ticket_id)


def _persist_generation_status(ticket_id: str, status: str) -> None:
    """Make graph progress visible without sharing a database session across nodes."""
    with Session(inventory_engine()) as session:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            raise LookupError("RFP ticket disappeared during response generation")
        ticket.status = RfpTicketStatus(status)
        ticket.updated_at = datetime.now(UTC)
        session.add(ticket)
        session.commit()


def persist_response_result(session: Session, result: ResponseResult) -> None:
    """Persist every last draft and its structured evaluation atomically."""
    ticket = session.get(RfpTicket, result.ticket_id)
    if ticket is None:
        raise LookupError("RFP ticket disappeared during response generation")
    stored_sections = {
        section.department_id: section
        for section in session.exec(
            select(DepartmentSection).where(DepartmentSection.ticket_id == result.ticket_id)
        ).all()
    }
    for generated in result.sections:
        section = stored_sections.get(generated["department_id"])
        if section is None:
            raise LookupError(f"Missing department section {generated['department_id']!r}")
        section.draft_content = generated["draft_content"]
        section.evaluation_results = generated["evaluation_result"]
        section.approval_status = (
            "needs_human_review"
            if generated.get("needs_human_review")
            else "ready_for_approval"
        )
        session.add(section)
    ticket.status = RfpTicketStatus(result.status)
    ticket.handoff_payload = result.handoff_payload
    ticket.ready_for_generation = False
    ticket.processing_error = None
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()


def generate_ticket_background(ticket_id: str, handoff_payload: dict[str, Any]) -> None:
    try:
        runtime = build_response_graph(
            on_status=lambda status: _persist_generation_status(ticket_id, status)
        )
        runtime_result = runtime.invoke(handoff_payload)
        with Session(inventory_engine()) as session:
            persist_response_result(session, runtime_result)
    except Exception:
        logger.exception("RFP response generation failed for ticket %s", ticket_id)
        try:
            with Session(inventory_engine()) as session:
                ticket = session.get(RfpTicket, ticket_id)
                if ticket:
                    ticket.processing_error = "Response generation failed; retry required."
                    ticket.updated_at = datetime.now(UTC)
                    session.add(ticket)
                    session.commit()
        except Exception:
            logger.exception("Could not persist RFP generation failure for %s", ticket_id)


@router.post("", status_code=202)
async def upload_rfp(
    background_tasks: BackgroundTasks,
    document: UploadFile = File(...),
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    filename = document.filename or ""
    if document.content_type != "application/pdf" or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF RFP document.")
    content = await document.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="The PDF exceeds the 12 MB limit.")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

    ticket_id = str(uuid4())
    raw_dir = _raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{ticket_id}.pdf"
    raw_path.write_bytes(content)
    now = datetime.now(UTC)
    ticket = RfpTicket(
        ticket_id=ticket_id,
        status=RfpTicketStatus.ANALYZING,
        raw_pdf_path=str(raw_path),
        created_by=str(caller.id),
        created_at=now,
        updated_at=now,
    )
    session.add(ticket)
    session.commit()
    background_tasks.add_task(process_ticket_background, ticket_id, str(raw_path))
    return {"ticket_id": ticket_id, "status": RfpTicketStatus.ANALYZING.value}


@router.get("")
def list_rfp_tickets(
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    statement = select(RfpTicket).order_by(RfpTicket.created_at.desc())
    tickets = session.exec(statement).all()
    return [_ticket_payload(session, ticket) for ticket in tickets if _can_read(ticket, caller)]


@router.post("/{ticket_id}/generate", status_code=202)
def start_response_generation(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Start Part 2 from the persisted Part 1 handoff; never re-read the PDF."""
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or not _can_read(ticket, caller):
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    if ticket.status != RfpTicketStatus.INTAKE_COMPLETE:
        raise HTTPException(
            status_code=409,
            detail="Response generation requires an intake-complete ticket.",
        )
    handoff = ticket.handoff_payload
    if not handoff.get("ticket_id") or not handoff.get("workstreams"):
        raise HTTPException(status_code=409, detail="The Part 1 routing handoff is incomplete.")
    ticket.status = RfpTicketStatus.DRAFTING
    ticket.processing_error = None
    ticket.updated_at = datetime.now(UTC)
    session.add(ticket)
    session.commit()
    background_tasks.add_task(generate_ticket_background, ticket_id, handoff)
    return {"ticket_id": ticket_id, "status": RfpTicketStatus.DRAFTING.value}


@router.get("/{ticket_id}")
def get_rfp_ticket(
    ticket_id: str,
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or not _can_read(ticket, caller):
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    return _ticket_payload(session, ticket)
