"""TrackFlow RFP response generation and structured self-evaluation.

Part 2 consumes only the persisted Part 1 handoff.  It never reads the source
PDF.  Department generators work independently, evaluator agents run in
parallel, and failed sections loop with actionable feedback up to a bounded
iteration count.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .pipeline import DEPARTMENTS, compute_readability

MAX_GENERATION_ITERATIONS = 3


class ResponseState(TypedDict, total=False):
    ticket_id: str
    metadata: dict[str, Any]
    workstreams: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    status: str
    handoff_payload: dict[str, Any]


Generator = Callable[[dict[str, Any], list[str], str, int], str]
StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class ResponseResult:
    ticket_id: str
    status: str
    sections: list[dict[str, Any]]
    handoff_payload: dict[str, Any]


def _common_terms(metadata: dict[str, Any]) -> str:
    volume = metadata.get("monthly_volume")
    volume_text = f"The current planning volume is {volume:,} orders per month." if volume else (
        "Monthly volume remains an open question and must be confirmed before contracting."
    )
    return f"""
### Commercial commitments

All pricing in this section is quoted in **{metadata['currency']}** for operations in
{metadata['client_country']}. TrackFlow commits to a **98.5% on-time delivery SLA**,
measured monthly. {volume_text} Final prices are client-facing totals and do not
disclose negotiated rates with any specific carrier.

| Monthly volume | Discount |
| --- | ---: |
| 0-4,999 orders | 0% |
| 5,000-9,999 orders | 3% |
| 10,000+ orders | 6% |
""".strip()


def _aspects(key_aspects: list[str]) -> str:
    return "\n".join(f"- {aspect}" for aspect in key_aspects)


def generate_warehouse_section(
    metadata: dict[str, Any], key_aspects: list[str], feedback: str, iteration: int
) -> str:
    revision = f"\nRevision {iteration} addresses: {feedback}\n" if feedback else ""
    return f"""## Warehouse Operations

TrackFlow will confirm storage capacity by SKU and pallet, receiving requirements,
and the onboarding plan before launch. The operating design covers inbound receipt,
put-away, cycle counting, pick-and-pack, and controlled inventory handoff. Capacity
is not assumed where the RFP is silent; the open questions below must be resolved.

### RFP requirements and open questions
{_aspects(key_aspects)}

### Warehouse offer

The final schedule will state storage cost per pallet or SKU, receiving cost, and
onboarding lead time. Capacity will be reserved only after the client confirms its
monthly order profile and SKU mix.{revision}

{_common_terms(metadata)}
""".strip()


def generate_lastmile_section(
    metadata: dict[str, Any], key_aspects: list[str], feedback: str, iteration: int
) -> str:
    revision = f"\nRevision {iteration} addresses: {feedback}\n" if feedback else ""
    return f"""## Last Mile and Carrier Management

TrackFlow will provide a final cost per shipment and select available carriers by
destination, service level, parcel profile, and capacity. The client receives one
TrackFlow price; confidential carrier agreements and negotiated carrier rates are
never disclosed. Delivery performance is reviewed against the committed SLA.

### RFP requirements and open questions
{_aspects(key_aspects)}

### Last-mile offer

Shipment pricing will be finalized after destination mix, weight bands, and peak
volume are confirmed. Carrier selection remains operationally flexible so TrackFlow
can protect delivery continuity and on-time performance.{revision}

{_common_terms(metadata)}
""".strip()


def generate_reverse_section(
    metadata: dict[str, Any], key_aspects: list[str], feedback: str, iteration: int
) -> str:
    revision = f"\nRevision {iteration} addresses: {feedback}\n" if feedback else ""
    return f"""## Reverse Logistics

TrackFlow will receive, inspect, grade, and route returned products for restock,
refurbishment, quarantine, or disposal according to the client's disposition rules.
Returns processing has a turnaround of **at least 48 hours** after physical receipt;
no shorter commitment is offered.

### RFP requirements and open questions
{_aspects(key_aspects)}

### Returns offer

The final schedule will state the processing cost per return and any separate
refurbishment or disposal charges. Reporting will show reason codes, disposition,
and time to completion without exposing personal customer data.{revision}

{_common_terms(metadata)}
""".strip()


DEFAULT_GENERATORS: Mapping[str, Generator] = {
    "warehouse": generate_warehouse_section,
    "lastmile": generate_lastmile_section,
    "reverse": generate_reverse_section,
}


def evaluate_readability(content: str) -> dict[str, Any]:
    metrics = compute_readability(content)
    score = float(metrics["flesch_kincaid_grade"])
    passed = int(metrics["word_count"]) >= 80 and score <= 22
    return {
        "pass": passed,
        "score": score,
        "details": {
            **metrics,
            "target": "at least 80 words and Flesch-Kincaid grade <= 22",
        },
    }


RELEVANCE_TERMS = {
    "warehouse": {
        "storage capacity": ("capacity", "storage"),
        "cost basis": ("cost per pallet", "cost per", "storage cost"),
        "onboarding": ("onboarding",),
    },
    "lastmile": {
        "shipment cost": ("cost per shipment", "shipment pricing"),
        "carrier availability": ("carrier", "destination"),
        "delivery SLA": ("delivery", "sla"),
    },
    "reverse": {
        "returns processing": ("returns processing", "returned products"),
        "turnaround": ("48 hours",),
        "restock/disposition": ("restock", "disposition"),
    },
}


def evaluate_relevance(department_id: str, content: str) -> dict[str, Any]:
    lowered = content.lower()
    missing = [
        label
        for label, alternatives in RELEVANCE_TERMS[department_id].items()
        if not any(term in lowered for term in alternatives)
    ]
    return {"pass": not missing, "missing_aspects": missing}


def _currency_for(country: str) -> str | None:
    country = country.strip().lower()
    if country in {"usa", "us", "united states", "united states of america"}:
        return "USD"
    if country in {"spain", "españa", "espana"}:
        return "EUR"
    return None


def evaluate_compliance(metadata: dict[str, Any], content: str) -> dict[str, Any]:
    lowered = content.lower()
    expected_currency = _currency_for(str(metadata.get("client_country", "")))
    violations: list[str] = []
    rule_ids = [
        "TF-CURRENCY",
        "TF-ON-TIME-SLA",
        "TF-RETURNS-MIN-48H",
        "TF-VOLUME-DISCOUNT",
        "TF-CARRIER-CONFIDENTIALITY",
    ]
    if expected_currency is None or expected_currency not in content:
        currency = expected_currency or "the mapped currency"
        violations.append(f"TF-CURRENCY: quote the section in {currency}.")
    sla_pattern = (
        r"\b\d{2}(?:\.\d+)?%[^\n]{0,40}on-time delivery sla|"
        r"on-time delivery sla[^\n]{0,40}\b\d{2}(?:\.\d+)?%"
    )
    if not re.search(sla_pattern, lowered):
        violations.append("TF-ON-TIME-SLA: state a numeric on-time delivery SLA percentage.")
    if re.search(r"(?:under|less than|within)\s+(?:[0-3]?\d|4[0-7])\s*hours", lowered):
        violations.append("TF-RETURNS-MIN-48H: never promise returns processing under 48 hours.")
    if "monthly volume" not in lowered or "discount" not in lowered or "|" not in content:
        violations.append("TF-VOLUME-DISCOUNT: include a volume-based discount tier table.")
    if any(
        phrase in lowered
        for phrase in ("carrier pays us", "our carrier rate is", "negotiated carrier rate is")
    ):
        violations.append("TF-CARRIER-CONFIDENTIALITY: remove negotiated carrier-rate disclosure.")
    return {"pass": not violations, "rule_ids": rule_ids, "violations": violations}


def evaluate_section(
    department_id: str, metadata: dict[str, Any], content: str
) -> dict[str, Any]:
    """Run isolated evaluator agents concurrently, then merge their outputs."""
    jobs: tuple[Callable[[], dict[str, Any]], ...] = (
        lambda: evaluate_readability(content),
        lambda: evaluate_relevance(department_id, content),
        lambda: evaluate_compliance(metadata, content),
    )
    with ThreadPoolExecutor(max_workers=3) as executor:
        readability, relevance, compliance = list(executor.map(lambda job: job(), jobs))
    overall_pass = bool(readability["pass"] and relevance["pass"] and compliance["pass"])
    feedback: list[str] = []
    if not readability["pass"]:
        feedback.append("Expand the section to 80+ clear words and simplify long sentences.")
    if relevance["missing_aspects"]:
        feedback.append("Address: " + ", ".join(relevance["missing_aspects"]) + ".")
    feedback.extend(compliance["violations"])
    return {
        "department_id": department_id,
        "readability": readability,
        "relevance": relevance,
        "compliance": compliance,
        "overall_pass": overall_pass,
        "feedback_for_generator": " ".join(feedback),
    }


@dataclass(frozen=True)
class RfpResponseRuntime:
    graph: Any

    def invoke(self, handoff_payload: dict[str, Any]) -> ResponseResult:
        final = self.graph.invoke(
            {
                "ticket_id": handoff_payload["ticket_id"],
                "metadata": handoff_payload["metadata"],
                "workstreams": handoff_payload["workstreams"],
            }
        )
        return ResponseResult(
            ticket_id=final["ticket_id"],
            status=final["status"],
            sections=final["sections"],
            handoff_payload=final["handoff_payload"],
        )


def build_response_graph(
    generators: Mapping[str, Generator] | None = None,
    *,
    max_iterations: int = MAX_GENERATION_ITERATIONS,
    on_status: StatusCallback | None = None,
) -> RfpResponseRuntime:
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")
    generators = generators or DEFAULT_GENERATORS
    status_callback = on_status or (lambda _status: None)

    def prepare_node(state: ResponseState) -> ResponseState:
        status_callback("drafting")
        sections = [
            {
                "department_id": workstream["department_id"],
                "contact": workstream.get(
                    "contact", DEPARTMENTS[workstream["department_id"]]["owner"]
                ),
                "key_aspects": list(workstream.get("key_aspects", [])),
                "draft_content": "",
                "evaluation_result": None,
                "feedback_for_generator": "",
                "iteration": 0,
                "complete": False,
            }
            for workstream in state["workstreams"]
        ]
        return {"sections": sections, "status": "drafting"}

    def generate_node(state: ResponseState) -> ResponseState:
        status_callback("drafting")

        def generate(section: dict[str, Any]) -> dict[str, Any]:
            if section["complete"]:
                return section
            department_id = section["department_id"]
            if department_id not in generators:
                raise ValueError(f"No generator registered for department {department_id!r}")
            iteration = int(section["iteration"]) + 1
            draft = generators[department_id](
                state["metadata"],
                section["key_aspects"],
                section["feedback_for_generator"],
                iteration,
            )
            return {**section, "draft_content": draft, "iteration": iteration}

        with ThreadPoolExecutor(max_workers=max(1, len(state["sections"]))) as executor:
            sections = list(executor.map(generate, state["sections"]))
        return {"sections": sections, "status": "drafting"}

    def evaluate_node(state: ResponseState) -> ResponseState:
        status_callback("under_evaluation")

        def evaluate(section: dict[str, Any]) -> dict[str, Any]:
            if section["complete"]:
                return section
            result = evaluate_section(
                section["department_id"], state["metadata"], section["draft_content"]
            )
            exhausted = int(section["iteration"]) >= max_iterations
            return {
                **section,
                "evaluation_result": result,
                "feedback_for_generator": result["feedback_for_generator"],
                "complete": bool(result["overall_pass"] or exhausted),
                "needs_human_review": bool(not result["overall_pass"] and exhausted),
            }

        with ThreadPoolExecutor(max_workers=max(1, len(state["sections"]))) as executor:
            sections = list(executor.map(evaluate, state["sections"]))
        return {"sections": sections, "status": "under_evaluation"}

    def after_evaluation(state: ResponseState) -> str:
        all_complete = all(section["complete"] for section in state["sections"])
        return "finalize" if all_complete else "generate"

    def finalize_node(state: ResponseState) -> ResponseState:
        needs_review = any(section.get("needs_human_review") for section in state["sections"])
        final_status = "needs_human_review" if needs_review else "under_evaluation"
        status_callback(final_status)
        handoff_sections = [
            {
                "department_id": section["department_id"],
                "contact": section["contact"],
                "key_aspects": section["key_aspects"],
                "draft_content": section["draft_content"],
                "evaluation_result": section["evaluation_result"],
                "iteration_count": section["iteration"],
                "needs_human_review": bool(section.get("needs_human_review")),
            }
            for section in state["sections"]
        ]
        return {
            "status": final_status,
            "handoff_payload": {
                "ticket_id": state["ticket_id"],
                "metadata": state["metadata"],
                "sections": handoff_sections,
            },
        }

    workflow = StateGraph(ResponseState)
    workflow.add_node("prepare", prepare_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("finalize", finalize_node)
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "generate")
    workflow.add_edge("generate", "evaluate")
    workflow.add_conditional_edges(
        "evaluate", after_evaluation, {"generate": "generate", "finalize": "finalize"}
    )
    workflow.add_edge("finalize", END)
    return RfpResponseRuntime(workflow.compile())


_RUNTIME = build_response_graph()


def generate_response(handoff_payload: dict[str, Any]) -> ResponseResult:
    return _RUNTIME.invoke(handoff_payload)
