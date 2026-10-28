"""Persistent human approval branches and deterministic TrackFlow arbitration."""

from __future__ import annotations

import copy
import operator
import re
import sqlite3
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .pipeline import DEPARTMENTS
from .response import DEFAULT_GENERATORS, Generator, evaluate_section

MAX_APPROVAL_REVISIONS = 2
ApprovalDecision = Literal["approve", "reject", "request_changes"]


class ApprovalState(TypedDict, total=False):
    ticket_id: str
    department_id: str
    contact: str
    metadata: dict[str, Any]
    key_aspects: list[str]
    draft_content: str
    evaluation_result: dict[str, Any]
    iteration_count: int
    approval_revision_count: int
    approval_status: str
    approver: str | None
    decision_reason: str
    forced_decision: str | None
    arbitration: list[dict[str, Any]]
    trace: Annotated[list[dict[str, Any]], operator.add]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _trace(agent: str, input_data: Any, output_data: Any) -> list[dict[str, Any]]:
    return [
        {
            "agent": agent,
            "input": input_data,
            "output": output_data,
            "timestamp": _now(),
        }
    ]


def _country_currency(country: str) -> str | None:
    normalized = country.strip().lower()
    if normalized in {"usa", "us", "united states", "united states of america"}:
        return "USD"
    if normalized in {"spain", "españa", "espana"}:
        return "EUR"
    return None


def arbitrate_conflicts(
    metadata: dict[str, Any], sections: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve the three briefing triggers using their fixed human/rule arbiter."""
    adjusted_metadata = copy.deepcopy(metadata)
    adjusted_sections = copy.deepcopy(sections)
    conflicts: list[dict[str, Any]] = []
    expected_currency = _country_currency(str(metadata.get("client_country", "")))

    for section in adjusted_sections:
        currencies = set(re.findall(r"\b(?:USD|EUR)\b", section.get("draft_content", "")))
        quoted = section.get("quoted_currency")
        if quoted:
            currencies.add(str(quoted))
        if expected_currency and any(currency != expected_currency for currency in currencies):
            section["draft_content"] = re.sub(
                r"\b(?:USD|EUR)\b", expected_currency, section.get("draft_content", "")
            )
            section["quoted_currency"] = expected_currency
            conflicts.append(
                {
                    "trigger_id": "currency-mismatch",
                    "department_id": section["department_id"],
                    "arbiter": "Miguel Torres",
                    "resolution": f"Rewrote the section to {expected_currency}.",
                }
            )

        under_48 = re.search(
            r"(?:under|less than|within)\s+(?:[0-3]?\d|4[0-7])\s*hours",
            section.get("draft_content", "").lower(),
        )
        if under_48:
            arbiter = "Sofía Ramos" if section["department_id"] == "reverse" else "Miguel Torres"
            section["forced_decision"] = "request_changes"
            section["arbitration_feedback"] = (
                "Remove the under-48-hour returns promise before approval."
            )
            conflicts.append(
                {
                    "trigger_id": "returns-sla-breach",
                    "department_id": section["department_id"],
                    "arbiter": arbiter,
                    "resolution": "Forced request_changes until the 48-hour minimum is restored.",
                }
            )

    monthly_volume = metadata.get("monthly_volume")
    warehouse = next(
        (section for section in adjusted_sections if section["department_id"] == "warehouse"),
        None,
    )
    lastmile = next(
        (section for section in adjusted_sections if section["department_id"] == "lastmile"),
        None,
    )
    capacity = warehouse.get("committed_capacity") if warehouse else None
    if monthly_volume and capacity and lastmile and int(monthly_volume) > int(capacity):
        adjusted_metadata["monthly_volume"] = int(capacity)
        lastmile["quoted_volume"] = int(capacity)
        lastmile["forced_decision"] = "request_changes"
        lastmile["arbitration_feedback"] = (
            f"Revise shipment volume and cost to the warehouse capacity of {int(capacity):,}."
        )
        conflicts.append(
            {
                "trigger_id": "volume-vs-capacity",
                "department_id": "lastmile",
                "arbiter": "Miguel Torres",
                "resolution": f"Capped proposal volume at {int(capacity):,} orders per month.",
            }
        )
    return adjusted_metadata, adjusted_sections, conflicts


def _approval_graph(
    checkpointer: SqliteSaver,
    generators: Mapping[str, Generator],
    max_revisions: int,
):
    def prepare_node(state: ApprovalState) -> ApprovalState:
        output = {"approval_status": "pending", "approval_revision_count": 0}
        return {
            **output,
            "trace": _trace("approval_preparer", {"department_id": state["department_id"]}, output),
        }

    def ready_node(state: ApprovalState) -> ApprovalState:
        output = {
            "approval_status": "waiting_for_approval",
            "owner": state["contact"],
        }
        return {
            "approval_status": output["approval_status"],
            "trace": _trace("approval_gate", {"evaluation": state["evaluation_result"]}, output),
        }

    def human_node(state: ApprovalState) -> ApprovalState:
        response = interrupt(
            {
                "ticket_id": state["ticket_id"],
                "department_id": state["department_id"],
                "owner": state["contact"],
                "draft_content": state["draft_content"],
                "evaluation_result": state["evaluation_result"],
                "allowed_decisions": ["approve", "reject", "request_changes"],
            }
        )
        decision = str(response["decision"])
        reason = str(response.get("reason", "")).strip()
        approver = str(response["approver"])
        if decision not in {"approve", "reject", "request_changes"}:
            raise ValueError("Approval decision must be approve, reject, or request_changes")
        if approver != state["contact"]:
            raise ValueError(f"Only {state['contact']} may decide this department section")
        if state.get("forced_decision") == "request_changes" and decision == "approve":
            decision = "request_changes"
            reason = str(state.get("arbitration_feedback") or "Resolve the arbitration conflict.")
        if decision == "approve" and not state["evaluation_result"].get("overall_pass"):
            decision = "request_changes"
            reason = "Resolve all failed structured evaluations before approval."
        output = {"decision": decision, "reason": reason, "approver": approver}
        return {
            "approval_status": decision,
            "approver": approver,
            "decision_reason": reason,
            "trace": _trace("human_approval", {"owner": state["contact"]}, output),
        }

    def after_human(state: ApprovalState) -> str:
        if state["approval_status"] == "approve":
            return "approved"
        if state["approval_status"] == "reject":
            return "rejected"
        return "revise"

    def revise_node(state: ApprovalState) -> ApprovalState:
        revision_count = int(state.get("approval_revision_count", 0)) + 1
        if revision_count >= max_revisions:
            output = {
                "approval_status": "needs_human_review",
                "approval_revision_count": revision_count,
            }
            return {
                **output,
                "trace": _trace(
                    "revision_limit", {"reason": state.get("decision_reason")}, output
                ),
            }
        department_id = state["department_id"]
        draft = generators[department_id](
            state["metadata"],
            state["key_aspects"],
            state.get("decision_reason", ""),
            int(state.get("iteration_count", 0)) + revision_count,
        )
        evaluation = evaluate_section(department_id, state["metadata"], draft)
        output = {
            "approval_status": "revised",
            "approval_revision_count": revision_count,
            "draft_content": draft,
            "evaluation_result": evaluation,
            "forced_decision": None,
        }
        return {
            **output,
            "trace": _trace(
                "department_reviser",
                {"reason": state.get("decision_reason"), "revision": revision_count},
                {"overall_pass": evaluation["overall_pass"]},
            ),
        }

    def after_revision(state: ApprovalState) -> str:
        return "end" if state["approval_status"] == "needs_human_review" else "ready"

    def approved_node(state: ApprovalState) -> ApprovalState:
        output = {"approval_status": "approved"}
        return {**output, "trace": _trace("approval_finalizer", {}, output)}

    def rejected_node(state: ApprovalState) -> ApprovalState:
        output = {"approval_status": "rejected"}
        return {**output, "trace": _trace("approval_finalizer", {}, output)}

    workflow = StateGraph(ApprovalState)
    workflow.add_node("prepare", prepare_node)
    workflow.add_node("ready", ready_node)
    workflow.add_node("human", human_node)
    workflow.add_node("revise", revise_node)
    workflow.add_node("approved", approved_node)
    workflow.add_node("rejected", rejected_node)
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "ready")
    workflow.add_edge("ready", "human")
    workflow.add_conditional_edges(
        "human",
        after_human,
        {"approved": "approved", "rejected": "rejected", "revise": "revise"},
    )
    workflow.add_conditional_edges(
        "revise", after_revision, {"ready": "ready", "end": END}
    )
    workflow.add_edge("approved", END)
    workflow.add_edge("rejected", END)
    return workflow.compile(checkpointer=checkpointer)


@dataclass
class ApprovalCoordinator:
    checkpoint_path: Path
    generators: Mapping[str, Generator] = None  # type: ignore[assignment]
    max_revisions: int = MAX_APPROVAL_REVISIONS

    def __post_init__(self) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.generators = self.generators or DEFAULT_GENERATORS
        self._connection = sqlite3.connect(str(self.checkpoint_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._connection)
        self._checkpointer.setup()
        self._graph = _approval_graph(
            self._checkpointer, self.generators, self.max_revisions
        )

    @staticmethod
    def thread_id(ticket_id: str, department_id: str) -> str:
        return f"rfp-{ticket_id}:{department_id}"

    def _config(self, ticket_id: str, department_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id(ticket_id, department_id)}}

    def start(self, handoff_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        metadata, sections, conflicts = arbitrate_conflicts(
            handoff_payload["metadata"], handoff_payload["sections"]
        )

        def start_section(section: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            department_id = section["department_id"]
            related_conflicts = [
                conflict for conflict in conflicts if conflict["department_id"] == department_id
            ]
            initial: ApprovalState = {
                "ticket_id": handoff_payload["ticket_id"],
                "department_id": department_id,
                "contact": section.get("contact", DEPARTMENTS[department_id]["owner"]),
                "metadata": metadata,
                "key_aspects": list(section.get("key_aspects", [])),
                "draft_content": section["draft_content"],
                "evaluation_result": section["evaluation_result"],
                "iteration_count": int(section.get("iteration_count", 1)),
                "forced_decision": section.get("forced_decision"),
                "arbitration": related_conflicts,
                "trace": _trace(
                    "fixed_arbiter",
                    {"department_id": department_id},
                    {"conflicts": related_conflicts},
                ),
            }
            if section.get("arbitration_feedback"):
                initial["decision_reason"] = section["arbitration_feedback"]
            self._graph.invoke(
                initial,
                self._config(handoff_payload["ticket_id"], department_id),
            )
            return department_id, self.snapshot(handoff_payload["ticket_id"], department_id)

        with ThreadPoolExecutor(max_workers=max(1, len(sections))) as executor:
            return dict(executor.map(start_section, sections))

    def resume(
        self,
        ticket_id: str,
        department_id: str,
        decision: ApprovalDecision,
        approver: str,
        reason: str = "",
    ) -> dict[str, Any]:
        if decision not in {"approve", "reject", "request_changes"}:
            raise ValueError("Invalid approval decision")
        state = self.snapshot(ticket_id, department_id)
        if state.get("approval_status") != "waiting_for_approval":
            raise ValueError("This department is not waiting for approval")
        self._graph.invoke(
            Command(
                resume={"decision": decision, "approver": approver, "reason": reason}
            ),
            self._config(ticket_id, department_id),
        )
        return self.snapshot(ticket_id, department_id)

    def snapshot(self, ticket_id: str, department_id: str) -> dict[str, Any]:
        snapshot = self._graph.get_state(self._config(ticket_id, department_id))
        values = dict(snapshot.values)
        values["interrupted"] = any(task.interrupts for task in snapshot.tasks)
        values["thread_id"] = self.thread_id(ticket_id, department_id)
        return values

    def close(self) -> None:
        self._connection.close()


def synthesize_final_document(
    ticket_id: str,
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
) -> str:
    if not sections or any(section.get("approval_status") != "approved" for section in sections):
        raise ValueError("Every active department must approve before final synthesis")
    headings = [
        "# TrackFlow Logistics Proposal",
        "",
        f"**Ticket:** {ticket_id}",
        f"**Client:** {metadata['client_name']}",
        f"**Market and currency:** {metadata['client_country']} / {metadata['currency']}",
        f"**Generated:** {_now()}",
        "",
    ]
    for section in sections:
        headings.extend(
            [
                section["draft_content"],
                "",
                f"Approved by {section['approver']} ({section['department_id']}).",
                "",
            ]
        )
    return "\n".join(headings).strip() + "\n"
