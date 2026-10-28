from __future__ import annotations

from pathlib import Path

from rfp_intake import (
    build_intake_graph,
    classify_rfp,
    extract_metadata,
    run_department_worker,
)

FORMAL = """REQUEST FOR PROPOSAL (RFP)
Issuing Organization: ModaViva, S.L.
RFP Reference No.: MV-LOG-2026-03
Proposal Due Date: August 28, 2026
ModaViva is a Spanish ecommerce brand requesting almacenamiento of 15,000 SKUs
near Zaragoza and gestión de devoluciones. We maintain our own carrier and no
last mile service is required.
"""

INFORMAL = """Luna Cosmetics — Los Angeles, CA, USA
We're Luna Cosmetics, a skincare brand. We crossed 5,000 orders a month.
We need warehousing and shipping across the US, including carrier selection.
Could you send over a proposal? We need to launch (around August 24th).
"""

INVALID = """Subject: Exclusive shipping rates for TrackFlow
We would like to become one of TrackFlow's preferred carrier partners. We are
offering aggressive introductory rates for packages.
"""


def test_classifier_accepts_formal_and_informal_rfps_and_rejects_pitch():
    assert classify_rfp(FORMAL).valid is True
    assert classify_rfp(INFORMAL).valid is True
    invalid = classify_rfp(INVALID)
    assert invalid.valid is False
    assert invalid.reason == "supplier_pitch_not_client_rfp"


def test_formal_rfp_routes_only_warehouse_and_reverse():
    metadata = extract_metadata(FORMAL)
    assert metadata["client_name"] == "ModaViva, S.L."
    assert metadata["client_country"] == "Spain"
    assert metadata["currency"] == "EUR"
    assert metadata["departments_needed"] == ["warehouse", "reverse"]
    assert metadata["monthly_volume"] is None


def test_informal_rfp_routes_warehouse_and_lastmile_with_volume():
    metadata = extract_metadata(INFORMAL)
    assert metadata["client_name"] == "Luna Cosmetics"
    assert metadata["currency"] == "USD"
    assert metadata["monthly_volume"] == 5000
    assert metadata["deadline"] == "around August 24th"
    assert metadata["departments_needed"] == ["warehouse", "lastmile"]


def test_worker_records_missing_figure_as_open_question():
    section = run_department_worker(
        "warehouse",
        {"monthly_volume": None},
        ["Almacenamiento of approximately 15,000 SKUs."],
    )
    assert section["contact"] == "Ana Whitfield"
    assert "OPEN QUESTION: confirm monthly order volume." in section["key_aspects"]


def test_dedicated_graph_handoff_contains_ticket_and_scoped_workstreams(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv("RFP_MARKDOWN_DIR", str(tmp_path / "markdown"))
    pdf = tmp_path / "rfp.pdf"
    pdf.write_bytes(b"%PDF fixture")
    runtime = build_intake_graph(converter=lambda _path: INFORMAL)

    result = runtime.invoke("ticket-123", str(pdf))

    assert result.status == "intake_complete"
    assert result.handoff_payload["ticket_id"] == "ticket-123"
    assert [item["department_id"] for item in result.sections] == [
        "warehouse",
        "lastmile",
    ]
    assert result.handoff_payload["workstreams"] == result.sections
    assert Path(result.markdown_path).read_text() == INFORMAL


def test_invalid_graph_stops_before_workers(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RFP_MARKDOWN_DIR", str(tmp_path / "markdown"))
    runtime = build_intake_graph(converter=lambda _path: INVALID)
    result = runtime.invoke("ticket-invalid", str(tmp_path / "invalid.pdf"))
    assert result.status == "discarded"
    assert result.sections == []
    assert result.handoff_payload == {}
