from __future__ import annotations

from pathlib import Path

import pytest
from rfp_intake import (
    ApprovalCoordinator,
    arbitrate_conflicts,
    generate_response,
    synthesize_final_document,
)


def response_handoff() -> dict:
    part1 = {
        "ticket_id": "approval-ticket",
        "metadata": {
            "client_name": "ModaViva",
            "client_country": "Spain",
            "currency": "EUR",
            "monthly_volume": 5_000,
        },
        "workstreams": [
            {
                "department_id": "warehouse",
                "contact": "Ana Whitfield",
                "key_aspects": ["Confirm capacity and onboarding."],
            },
            {
                "department_id": "reverse",
                "contact": "Sofía Ramos",
                "key_aspects": ["Confirm returns processing."],
            },
        ],
    }
    return generate_response(part1).handoff_payload


def coordinator(tmp_path: Path, *, max_revisions: int = 2) -> ApprovalCoordinator:
    return ApprovalCoordinator(tmp_path / "approvals.sqlite3", max_revisions=max_revisions)


def test_each_department_interrupts_with_a_namespaced_persistent_checkpoint(
    tmp_path: Path,
) -> None:
    runtime = coordinator(tmp_path)
    states = runtime.start(response_handoff())
    try:
        assert set(states) == {"warehouse", "reverse"}
        assert all(state["interrupted"] for state in states.values())
        assert all(state["approval_status"] == "waiting_for_approval" for state in states.values())
        assert states["warehouse"]["thread_id"] == "rfp-approval-ticket:warehouse"
        assert states["reverse"]["thread_id"] == "rfp-approval-ticket:reverse"
    finally:
        runtime.close()

    reopened = coordinator(tmp_path)
    try:
        assert reopened.snapshot("approval-ticket", "warehouse")["interrupted"] is True
    finally:
        reopened.close()


def test_department_b_can_approve_while_department_a_remains_interrupted(
    tmp_path: Path,
) -> None:
    runtime = coordinator(tmp_path)
    runtime.start(response_handoff())
    try:
        reverse = runtime.resume(
            "approval-ticket", "reverse", "approve", "Sofía Ramos"
        )
        warehouse = runtime.snapshot("approval-ticket", "warehouse")
        assert reverse["approval_status"] == "approved"
        assert reverse["interrupted"] is False
        assert warehouse["approval_status"] == "waiting_for_approval"
        assert warehouse["interrupted"] is True
    finally:
        runtime.close()


def test_request_changes_resumes_exact_branch_and_enforces_revision_limit(
    tmp_path: Path,
) -> None:
    runtime = coordinator(tmp_path, max_revisions=2)
    runtime.start(response_handoff())
    try:
        revised = runtime.resume(
            "approval-ticket",
            "warehouse",
            "request_changes",
            "Ana Whitfield",
            "Clarify the capacity commitment.",
        )
        assert revised["approval_revision_count"] == 1
        assert revised["approval_status"] == "waiting_for_approval"
        assert revised["interrupted"] is True

        exhausted = runtime.resume(
            "approval-ticket",
            "warehouse",
            "request_changes",
            "Ana Whitfield",
            "Capacity is still unclear.",
        )
        assert exhausted["approval_revision_count"] == 2
        assert exhausted["approval_status"] == "needs_human_review"
        assert exhausted["interrupted"] is False
    finally:
        runtime.close()


def test_briefing_arbitration_uses_fixed_triggers_and_arbiters() -> None:
    metadata = {
        "client_name": "Luna",
        "client_country": "USA",
        "currency": "USD",
        "monthly_volume": 5_000,
    }
    sections = [
        {
            "department_id": "warehouse",
            "draft_content": "Capacity in EUR. Returns within 12 hours.",
            "committed_capacity": 4_000,
        },
        {
            "department_id": "lastmile",
            "draft_content": "Shipping in EUR.",
        },
    ]
    adjusted_metadata, adjusted_sections, conflicts = arbitrate_conflicts(metadata, sections)
    assert adjusted_metadata["monthly_volume"] == 4_000
    assert {conflict["trigger_id"] for conflict in conflicts} == {
        "currency-mismatch",
        "returns-sla-breach",
        "volume-vs-capacity",
    }
    assert all(conflict["arbiter"] in {"Miguel Torres", "Sofía Ramos"} for conflict in conflicts)
    assert adjusted_sections[0]["quoted_currency"] == "USD"
    assert adjusted_sections[1]["quoted_volume"] == 4_000


def test_final_document_requires_every_active_department_approval(tmp_path: Path) -> None:
    runtime = coordinator(tmp_path)
    payload = response_handoff()
    runtime.start(payload)
    try:
        reverse = runtime.resume(
            "approval-ticket", "reverse", "approve", "Sofía Ramos"
        )
        with pytest.raises(ValueError, match="Every active department"):
            synthesize_final_document(
                "approval-ticket",
                payload["metadata"],
                [reverse, runtime.snapshot("approval-ticket", "warehouse")],
            )
        warehouse = runtime.resume(
            "approval-ticket", "warehouse", "approve", "Ana Whitfield"
        )
        document = synthesize_final_document(
            "approval-ticket", payload["metadata"], [warehouse, reverse]
        )
        assert "# TrackFlow Logistics Proposal" in document
        assert "Approved by Ana Whitfield" in document
        assert "Approved by Sofía Ramos" in document
    finally:
        runtime.close()
