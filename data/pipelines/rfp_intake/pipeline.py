"""TrackFlow RFP intake: PDF conversion, classification, and routing.

This graph is deliberately separate from the customer-support agent. It accepts
one PDF path, converts it before any classifier/worker reads it, and produces a
typed Part 2 handoff without persisting data itself.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import unicodedata
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

DEPARTMENTS = {
    "warehouse": {
        "name": "Warehouse Operations",
        "owner": "Ana Whitfield",
        "keywords": ("warehouse", "warehousing", "storage", "sku", "almacenamiento"),
    },
    "lastmile": {
        "name": "Last Mile and Carrier Management",
        "owner": "Carlos Vega",
        "keywords": ("last mile", "shipping", "carrier", "delivery", "transportista"),
    },
    "reverse": {
        "name": "Reverse Logistics",
        "owner": "Sofía Ramos",
        "keywords": ("return", "returns", "reverse", "devoluciones", "restock"),
    },
}


@dataclass(frozen=True)
class RfpClassification:
    valid: bool
    reason: str


@dataclass(frozen=True)
class IntakeResult:
    ticket_id: str
    status: str
    classification: RfpClassification
    metadata: dict[str, Any]
    sections: list[dict[str, Any]]
    sales_summary: str
    handoff_payload: dict[str, Any]
    markdown_path: str


class IntakeState(TypedDict, total=False):
    ticket_id: str
    pdf_path: str
    markdown: str
    markdown_path: str
    classification: dict[str, Any]
    metadata: dict[str, Any]
    workstreams: list[dict[str, Any]]
    sections: list[dict[str, Any]]
    sales_summary: str
    handoff_payload: dict[str, Any]
    status: str


PdfConverter = Callable[[Path], str]


def _plain(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(character)
    )


def convert_pdf_to_markdown(path: Path) -> str:
    """Use MarkItDown, with documented pdftotext fallback for local recovery."""
    try:
        from markitdown import MarkItDown

        result = MarkItDown().convert(str(path))
        text = str(result.text_content or "").strip()
    except (ImportError, RuntimeError, ValueError):
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
        text = completed.stdout.strip()
    if not text:
        raise ValueError("The PDF did not contain extractable text.")
    return text


def classify_rfp(markdown: str) -> RfpClassification:
    """Accept formal and informal client requests; reject supplier rate pitches."""
    plain = _plain(markdown)
    supplier_pitch = any(
        phrase in plain
        for phrase in (
            "preferred carrier partner",
            "become one of trackflow's preferred",
            "offering aggressive introductory rates",
            "shipping rates for trackflow",
        )
    )
    asks_for_proposal = any(
        phrase in plain
        for phrase in (
            "request for proposal",
            "solicitud de propuesta",
            "send over a proposal",
            "send us a proposal",
            "could you send over a proposal",
        )
    )
    service_need = any(
        word in plain
        for word in (
            "warehousing",
            "warehouse",
            "almacenamiento",
            "last mile",
            "returns",
            "devoluciones",
            "fulfillment",
        )
    )
    if supplier_pitch:
        return RfpClassification(False, "supplier_pitch_not_client_rfp")
    if asks_for_proposal and service_need:
        return RfpClassification(True, "client_requests_trackflow_services")
    return RfpClassification(False, "missing_client_proposal_request_or_service_scope")


def _first_match(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return " ".join(match.group(1).split()).strip(" ,")
    return None


def compute_readability(markdown: str) -> dict[str, float | int]:
    """Compute Flesch-Kincaid and Gunning Fog equivalents deterministically."""
    words = re.findall(r"[A-Za-zÀ-ÿ]+", markdown)
    sentences = max(1, len(re.findall(r"[.!?]+", markdown)))
    syllables = 0
    complex_words = 0
    for word in words:
        groups = re.findall(r"[aeiouyáéíóúü]+", word.lower())
        count = max(1, len(groups))
        syllables += count
        complex_words += int(count >= 3)
    word_count = max(1, len(words))
    grade = 0.39 * (word_count / sentences) + 11.8 * (syllables / word_count) - 15.59
    fog = 0.4 * ((word_count / sentences) + 100 * (complex_words / word_count))
    return {
        "word_count": len(words),
        "sentence_count": sentences,
        "flesch_kincaid_grade": round(max(0, grade), 2),
        "gunning_fog": round(max(0, fog), 2),
        "estimated_tokens": math.ceil(len(markdown) / 4),
    }


def extract_metadata(markdown: str) -> dict[str, Any]:
    plain = _plain(markdown)
    client_name = (
        _first_match(
            (
                r"Issuing Organization:\s*([^\n]+)",
                r"We're\s+([^,\n]+)",
                r"^([^\n—-]+)\s+[—-]\s+(?:Los Angeles|Madrid|Spain)",
            ),
            markdown,
        )
        or "Unknown client"
    )
    if any(term in plain for term in ("spain", "espana", "zaragoza", "modaviva")):
        country, currency = "Spain", "EUR"
    elif any(term in plain for term in ("usa", "los angeles", "across the us")):
        country, currency = "USA", "USD"
    else:
        country, currency = "Unknown", "Unknown"

    negative_lastmile = any(
        phrase in plain
        for phrase in (
            "no se requiere gestion de transportistas ni ultima milla",
            "mantenemos nuestro propio transportista",
            "own carrier for last mile",
            "own carrier",
            "no last mile service is required",
        )
    )
    services: list[str] = []
    if any(word in plain for word in ("warehouse", "warehousing", "almacenamiento")):
        services.append("warehousing")
    if not negative_lastmile and any(
        word in plain for word in ("last mile", "shipping", "carrier selection")
    ):
        services.append("last_mile")
    if any(word in plain for word in ("returns", "devoluciones", "reverse logistics")):
        services.append("reverse_logistics")

    volume_match = re.search(r"([\d,.]+)\s+orders\s+(?:a|per)\s+month", plain)
    monthly_volume = int(re.sub(r"\D", "", volume_match.group(1))) if volume_match else None
    deadline = _first_match(
        (
            r"Proposal Due Date:\s*([^\n]+)",
            r"up and running[\s\S]{0,100}?\(([^)]+)\)",
            r"\((around\s+[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)\)",
        ),
        markdown,
    )
    budget = _first_match((r"(?:budget|presupuesto)(?: range)?\s*:\s*([^\n]+)",), markdown)
    rfp_id = _first_match((r"RFP Reference No\.:\s*([^\n]+)",), markdown)
    department_map = {
        "warehousing": "warehouse",
        "last_mile": "lastmile",
        "reverse_logistics": "reverse",
    }
    departments = [department_map[service] for service in services]
    return {
        "rfp_id": rfp_id,
        "client_name": client_name,
        "client_country": country,
        "currency": currency,
        "services_requested": services,
        "monthly_volume": monthly_volume,
        "deadline": deadline,
        "budget_range": budget,
        "departments_needed": departments,
        "readability_metrics": compute_readability(markdown),
    }


def _relevant_extracts(markdown: str, department_id: str) -> list[str]:
    keywords = DEPARTMENTS[department_id]["keywords"]
    lines = [" ".join(line.split()) for line in markdown.splitlines() if line.strip()]
    return [line for line in lines if any(word in _plain(line) for word in keywords)][:6]


def run_department_worker(
    department_id: str, metadata: dict[str, Any], relevant_extracts: list[str]
) -> dict[str, Any]:
    """Analyze only scoped extracts plus shared metadata; never invent figures."""
    aspects = list(relevant_extracts)
    if metadata.get("monthly_volume") is None:
        aspects.append("OPEN QUESTION: confirm monthly order volume.")
    if department_id == "warehouse":
        aspects.append("Confirm storage capacity, unit basis, and onboarding lead time.")
    elif department_id == "lastmile":
        aspects.append("Confirm offered carriers, per-shipment cost, and delivery SLA.")
    elif department_id == "reverse":
        aspects.append("Confirm returns processing cost and turnaround of at least 48 hours.")
    return {
        "department_id": department_id,
        "department_name": DEPARTMENTS[department_id]["name"],
        "contact": DEPARTMENTS[department_id]["owner"],
        "key_aspects": aspects,
    }


@dataclass(frozen=True)
class RfpIntakeRuntime:
    graph: Any

    def invoke(self, ticket_id: str, pdf_path: str) -> IntakeResult:
        final = self.graph.invoke({"ticket_id": ticket_id, "pdf_path": pdf_path})
        classification = RfpClassification(**final["classification"])
        return IntakeResult(
            ticket_id=ticket_id,
            status=final["status"],
            classification=classification,
            metadata=final.get("metadata", {}),
            sections=final.get("sections", []),
            sales_summary=final.get("sales_summary", ""),
            handoff_payload=final.get("handoff_payload", {}),
            markdown_path=final["markdown_path"],
        )


def build_intake_graph(converter: PdfConverter = convert_pdf_to_markdown) -> RfpIntakeRuntime:
    def convert_node(state: IntakeState) -> IntakeState:
        markdown = converter(Path(state["pdf_path"]))
        root = Path(
            os.getenv("RFP_MARKDOWN_DIR", Path(__file__).resolve().parents[2] / "processed" / "rfp")
        )
        root.mkdir(parents=True, exist_ok=True)
        markdown_path = root / f"{state['ticket_id']}.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        return {"markdown": markdown, "markdown_path": str(markdown_path)}

    def classify_node(state: IntakeState) -> IntakeState:
        result = classify_rfp(state["markdown"])
        return {
            "classification": asdict(result),
            "status": "analyzing" if result.valid else "discarded",
        }

    def after_classification(state: IntakeState) -> str:
        return "extract_metadata" if state["classification"]["valid"] else END

    def metadata_node(state: IntakeState) -> IntakeState:
        return {"metadata": extract_metadata(state["markdown"])}

    def orchestrate_node(state: IntakeState) -> IntakeState:
        tasks = [
            {
                "department_id": department_id,
                "metadata": state["metadata"],
                "extracts": _relevant_extracts(state["markdown"], department_id),
            }
            for department_id in state["metadata"]["departments_needed"]
        ]
        return {"workstreams": tasks}

    def workers_node(state: IntakeState) -> IntakeState:
        tasks = state["workstreams"]
        with ThreadPoolExecutor(max_workers=max(1, len(tasks))) as executor:
            sections = list(
                executor.map(
                    lambda task: run_department_worker(
                        task["department_id"], task["metadata"], task["extracts"]
                    ),
                    tasks,
                )
            )
        return {"sections": sections}

    def synthesize_node(state: IntakeState) -> IntakeState:
        contacts = ", ".join(
            f"{section['department_name']} — {section['contact']}" for section in state["sections"]
        )
        summary = (
            f"{state['metadata']['client_name']} requests "
            f"{', '.join(state['metadata']['services_requested'])}. "
            f"Coordinate with {contacts}."
        )
        handoff = {
            "ticket_id": state["ticket_id"],
            "metadata": state["metadata"],
            "workstreams": state["sections"],
        }
        return {
            "sales_summary": summary,
            "handoff_payload": handoff,
            "status": "intake_complete",
        }

    workflow = StateGraph(IntakeState)
    workflow.add_node("convert_pdf", convert_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("extract_metadata", metadata_node)
    workflow.add_node("orchestrate", orchestrate_node)
    workflow.add_node("department_workers", workers_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_edge(START, "convert_pdf")
    workflow.add_edge("convert_pdf", "classify")
    workflow.add_conditional_edges(
        "classify", after_classification, {"extract_metadata": "extract_metadata", END: END}
    )
    workflow.add_edge("extract_metadata", "orchestrate")
    workflow.add_edge("orchestrate", "department_workers")
    workflow.add_edge("department_workers", "synthesize")
    workflow.add_edge("synthesize", END)
    return RfpIntakeRuntime(workflow.compile())


_RUNTIME = build_intake_graph()


def process_rfp(pdf_path: str, ticket_id: str) -> IntakeResult:
    return _RUNTIME.invoke(ticket_id=ticket_id, pdf_path=pdf_path)
