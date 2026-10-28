from __future__ import annotations

from pathlib import Path

import pytest
from trackflow_agent import (
    Decision,
    MemoryCandidate,
    MemoryStore,
    classify_decision,
    contains_forbidden_memory,
    evaluate_memory_candidate,
)


@pytest.mark.parametrize(
    ("message", "category"),
    [
        (
            "SEUR no longer covers rural Zaragoza, so we must use the local carrier.",
            "carrier_rule",
        ),
        (
            "This is the third ticket this week: delays in Zaragoza are due to flooding.",
            "recurring_incident",
        ),
        (
            "The Acme B2B client always wants its monthly report grouped by carrier.",
            "b2b_report_preference",
        ),
    ],
)
def test_evaluator_proposes_only_briefing_approved_classes(message: str, category: str):
    candidate = evaluate_memory_candidate(message)
    assert candidate is not None
    assert candidate.category == category


@pytest.mark.parametrize(
    "message",
    [
        "Package 882 is late once today.",
        "Deliver the B2C parcel to 42 Main Street.",
        "Our commercial contract negotiation with UPS is active.",
    ],
)
def test_evaluator_rejects_one_off_sensitive_and_commercial_details(message: str):
    assert evaluate_memory_candidate(message) is None


def test_sensitive_location_detection_covers_b2c_and_warehouse_routes():
    assert contains_forbidden_memory("B2C address is 42 Main Street")
    assert contains_forbidden_memory("Use warehouse route Bay 7")


@pytest.mark.parametrize(
    ("message", "label"),
    [
        ("Yes, remember it", "approve"),
        ("reject", "reject"),
        ("edit: SEUR changed its coverage in Spain", "edit"),
        ("sounds fine", "ambiguous"),
    ],
)
def test_decision_classifier_requires_explicit_language(message: str, label: str):
    assert classify_decision(message).label == label


def _candidate(fact: str | None = None) -> MemoryCandidate:
    return MemoryCandidate(
        category="carrier_rule",
        scope_key="spain:seur",
        fact=fact or "SEUR no longer covers rural Zaragoza, so use the local carrier.",
        rationale="Corrected carrier coverage rule.",
    )


def test_approved_proposal_is_persisted_and_searchable(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    proposal = store.propose(
        user_id="7", run_id="run-1", originating_message="correction", candidate=_candidate()
    )
    record = store.resolve(proposal, Decision(label="approve"), "approve")

    assert record is not None
    assert store.pending("7") is None
    assert [item.fact for item in store.search("7", "SEUR Zaragoza")] == [record.fact]
    assert store.proposal_log("7")[0]["status"] == "approved"


@pytest.mark.parametrize("decision", ["reject", "ambiguous"])
def test_rejected_or_ambiguous_proposal_never_enters_memory(tmp_path: Path, decision: str):
    store = MemoryStore(tmp_path / f"{decision}.db")
    proposal = store.propose(
        user_id="7", run_id="run-1", originating_message="correction", candidate=_candidate()
    )
    store.resolve(proposal, Decision(label=decision), decision)

    assert store.list_memories("7") == []
    expected = "rejected" if decision == "reject" else "ambiguous_rejected"
    assert store.proposal_log("7")[0]["status"] == expected


def test_only_one_pending_proposal_exists_per_user(tmp_path: Path):
    store = MemoryStore(tmp_path / "one-pending.db")
    first = store.propose(
        user_id="7", run_id="one", originating_message="first", candidate=_candidate()
    )
    second = store.propose(
        user_id="7", run_id="two", originating_message="second", candidate=_candidate()
    )
    assert second.proposal_id == first.proposal_id


def test_edited_proposal_must_still_match_safe_memory_policy(tmp_path: Path):
    store = MemoryStore(tmp_path / "edited.db")
    proposal = store.propose(
        user_id="7", run_id="one", originating_message="first", candidate=_candidate()
    )
    result = store.resolve(
        proposal,
        Decision(label="edit", edited_fact="Deliver it to 42 Main Street"),
        "edit: Deliver it to 42 Main Street",
    )
    assert result is None
    assert store.list_memories("7") == []
    assert store.proposal_log("7")[0]["status"] == "rejected"
