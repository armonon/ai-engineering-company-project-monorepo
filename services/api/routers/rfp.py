"""Existing-API boundary for the asynchronous TrackFlow RFP workflow."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from rfp_intake import (
    ApprovalCoordinator,
    ApprovalDecision,
    IntakeResult,
    ResponseResult,
    build_response_graph,
    process_rfp,
    synthesize_final_document,
)
from sqlmodel import Session, select

from agent_observability import change_status, record_task, start_flow
from database import get_db, inventory_engine
from models import (
    DepartmentSection,
    FinalRfpDocument,
    ObservedTask,
    RfpMetadataRecord,
    RfpTicket,
    RfpTicketStatus,
    UserInDB,
)
from security import get_current_user

logger = logging.getLogger("trackflow.rfp")
router = APIRouter(prefix="/rfp/tickets", tags=["rfp-workflow"])
MAX_PDF_BYTES = 12 * 1024 * 1024


class ApprovalDecisionRequest(BaseModel):
    decision: ApprovalDecision
    reason: str = Field(default="", max_length=2_000)


def _raw_dir() -> Path:
    default = Path(__file__).resolve().parents[3] / "data" / "raw"
    return Path(os.getenv("RFP_RAW_DIR", default))


def _checkpoint_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "data" / "checkpoints" / "rfp.sqlite3"
    return Path(os.getenv("RFP_CHECKPOINT_DB", default))


def _can_read(ticket: RfpTicket, caller: UserInDB) -> bool:
    return caller.role.value in {"admin", "manager"} or ticket.created_by == str(caller.id)


def _observe_rfp_stage(
    ticket_id: str,
    tasks: list[tuple[str, str | None, dict[str, Any]]],
    *,
    status: str | None = None,
) -> None:
    """Best-effort instrumentation; observability cannot break the RFP flow."""
    try:
        with Session(inventory_engine()) as observation_session:
            flow_id = f"rfp-{ticket_id}"
            start_flow(
                observation_session,
                flow_id=flow_id,
                flow_type="rfp_workflow",
                triggered_by=f"rfp_ticket:{ticket_id}",
                agent_ids=["rfp_pipeline"],
            )
            previous = observation_session.exec(
                select(ObservedTask)
                .where(ObservedTask.flow_id == flow_id)
                .order_by(ObservedTask.created_at.desc())
            ).first()
            previous_id = previous.task_id if previous else None
            for action_type, department_id, payload in tasks:
                task = record_task(
                    observation_session,
                    flow_id=flow_id,
                    agent_id="rfp_pipeline",
                    action_type=action_type,
                    trigger=previous_id or f"external:rfp_ticket:{ticket_id}",
                    previous_task_id=previous_id,
                    department_id=department_id,
                    payload=payload,
                )
                previous_id = task.task_id
            if status:
                change_status(
                    observation_session,
                    flow_id=flow_id,
                    agent_id="rfp_pipeline",
                    status=status,
                )
    except Exception:
        logger.exception("Could not persist RFP observability events for %s", ticket_id)


def _ticket_payload(session: Session, ticket: RfpTicket) -> dict[str, Any]:
    metadata = session.exec(
        select(RfpMetadataRecord).where(RfpMetadataRecord.ticket_id == ticket.ticket_id)
    ).first()
    sections = session.exec(
        select(DepartmentSection)
        .where(DepartmentSection.ticket_id == ticket.ticket_id)
        .order_by(DepartmentSection.department_id)
    ).all()
    final_document = session.exec(
        select(FinalRfpDocument).where(FinalRfpDocument.ticket_id == ticket.ticket_id)
    ).first()
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
        "final_document": (
            {
                "generated_at": final_document.generated_at,
                "currency": final_document.currency,
                "content": final_document.content,
            }
            if final_document
            else None
        ),
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
        observed_tasks: list[tuple[str, str | None, dict[str, Any]]] = [
            ("query", None, {"stage": "classify_extract", "valid": result.classification.valid})
        ]
        observed_tasks.extend(
            ("tool_call", section["department_id"], {"stage": "department_routing"})
            for section in result.sections
        )
        observed_tasks.append(("deliver", None, {"stage": "intake_handoff"}))
        _observe_rfp_stage(ticket_id, observed_tasks)
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
        observed_tasks = []
        for section in runtime_result.sections:
            department_id = section["department_id"]
            observed_tasks.extend(
                [
                    ("draft_start", department_id, {"stage": "response_generation"}),
                    (
                        "write",
                        department_id,
                        {"iteration": section["iteration"]},
                    ),
                    (
                        "evaluate",
                        department_id,
                        {
                            "overall_pass": section["evaluation_result"]["overall_pass"],
                            "iteration": section["iteration"],
                        },
                    ),
                ]
            )
        observed_tasks.append(("deliver", None, {"stage": "approval_handoff"}))
        _observe_rfp_stage(ticket_id, observed_tasks)
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


def _approval_coordinator() -> ApprovalCoordinator:
    return ApprovalCoordinator(_checkpoint_path())


def _persist_approval_state(
    session: Session, ticket: RfpTicket, states: dict[str, dict[str, Any]]
) -> None:
    resolved_metadata = next(iter(states.values())).get(
        "metadata", ticket.handoff_payload["metadata"]
    )
    sections = {
        section.department_id: section
        for section in session.exec(
            select(DepartmentSection).where(DepartmentSection.ticket_id == ticket.ticket_id)
        ).all()
    }
    for department_id, state in states.items():
        section = sections.get(department_id)
        if section is None:
            raise LookupError(f"Missing department section {department_id!r}")
        section.draft_content = state["draft_content"]
        section.evaluation_results = state["evaluation_result"]
        section.approval_status = state["approval_status"]
        section.approver = state.get("approver")
        section.approved_at = (
            datetime.now(UTC) if state["approval_status"] == "approved" else None
        )
        session.add(section)

    statuses = {state["approval_status"] for state in states.values()}
    if statuses == {"approved"}:
        metadata = resolved_metadata
        ordered = [states[section.department_id] for section in sections.values()]
        content = synthesize_final_document(ticket.ticket_id, metadata, ordered)
        final_document = session.exec(
            select(FinalRfpDocument).where(FinalRfpDocument.ticket_id == ticket.ticket_id)
        ).first()
        if final_document is None:
            final_document = FinalRfpDocument(
                ticket_id=ticket.ticket_id,
                sections=ordered,
                currency=metadata["currency"],
                content=content,
            )
        else:
            final_document.sections = ordered
            final_document.currency = metadata["currency"]
            final_document.content = content
            final_document.generated_at = datetime.now(UTC)
        session.add(final_document)
        ticket.status = RfpTicketStatus.DONE
    elif "waiting_for_approval" in statuses:
        ticket.status = RfpTicketStatus.WAITING_FOR_APPROVAL
    else:
        ticket.status = RfpTicketStatus.NEEDS_HUMAN_REVIEW
    ticket.updated_at = datetime.now(UTC)
    ticket.handoff_payload = {
        **ticket.handoff_payload,
        "metadata": resolved_metadata,
        "approval_states": {
            department_id: {
                "thread_id": state["thread_id"],
                "approval_status": state["approval_status"],
                "approver": state.get("approver"),
                "trace": state.get("trace", []),
            }
            for department_id, state in states.items()
        },
    }
    session.add(ticket)
    session.commit()


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


@router.post("/{ticket_id}/approval/start")
def start_approval(
    ticket_id: str,
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or not _can_read(ticket, caller):
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    if ticket.status not in {
        RfpTicketStatus.UNDER_EVALUATION,
        RfpTicketStatus.NEEDS_HUMAN_REVIEW,
    }:
        raise HTTPException(
            status_code=409,
            detail="Approval requires the Part 2 generation handoff.",
        )
    if not ticket.handoff_payload.get("sections"):
        raise HTTPException(status_code=409, detail="The Part 2 handoff is incomplete.")
    coordinator = _approval_coordinator()
    try:
        states = coordinator.start(ticket.handoff_payload)
    finally:
        coordinator.close()
    _persist_approval_state(session, ticket, states)
    _observe_rfp_stage(ticket_id, [], status="waiting_for_human")
    return {
        "ticket_id": ticket_id,
        "status": ticket.status.value,
        "departments": {
            department_id: state["approval_status"]
            for department_id, state in states.items()
        },
    }


@router.post("/{ticket_id}/approval/{department_id}")
def resume_approval(
    ticket_id: str,
    department_id: str,
    body: ApprovalDecisionRequest,
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or not _can_read(ticket, caller):
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    section = session.exec(
        select(DepartmentSection).where(
            DepartmentSection.ticket_id == ticket_id,
            DepartmentSection.department_id == department_id,
        )
    ).first()
    if section is None:
        raise HTTPException(status_code=404, detail="RFP department section not found.")
    coordinator = _approval_coordinator()
    try:
        try:
            coordinator.resume(
                ticket_id,
                department_id,
                body.decision,
                section.contact,
                body.reason,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        departments = session.exec(
            select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)
        ).all()
        states = {
            item.department_id: coordinator.snapshot(ticket_id, item.department_id)
            for item in departments
        }
    finally:
        coordinator.close()
    _persist_approval_state(session, ticket, states)
    if ticket.status == RfpTicketStatus.DONE:
        _observe_rfp_stage(
            ticket_id,
            [("deliver", None, {"stage": "final_document"})],
            status="completed",
        )
    elif ticket.status == RfpTicketStatus.WAITING_FOR_APPROVAL:
        _observe_rfp_stage(ticket_id, [], status="waiting_for_human")
    return {
        "ticket_id": ticket_id,
        "status": ticket.status.value,
        "department_id": department_id,
        "approval_status": states[department_id]["approval_status"],
    }


@router.get("/{ticket_id}/final-document")
def get_final_document(
    ticket_id: str,
    caller: UserInDB = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None or not _can_read(ticket, caller):
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    document = session.exec(
        select(FinalRfpDocument).where(FinalRfpDocument.ticket_id == ticket_id)
    ).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Final document is not available yet.")
    return {
        "ticket_id": ticket_id,
        "currency": document.currency,
        "generated_at": document.generated_at,
        "content": document.content,
    }


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
