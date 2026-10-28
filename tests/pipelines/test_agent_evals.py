"""Offline evals inspect exported traces rather than rerunning a live model."""

from __future__ import annotations

import json
from pathlib import Path

TRACES = json.loads(
    (Path(__file__).parent / "fixtures" / "agent-traces.json").read_text(encoding="utf-8")
)


def by_name(name: str) -> dict:
    return next(case for case in TRACES if case["name"] == name)


def test_eval_empty_question_never_retrieves():
    case = by_name("empty question stops before retrieval")
    assert [event["node"] for event in case["trace"]] == ["receive", "invalid_question"]


def test_eval_no_context_is_honest_and_never_generates():
    case = by_name("unknown policy takes honest no-context route")
    assert case["answer"] == "I don't have enough verified TrackFlow information to answer that."
    assert [event["node"] for event in case["trace"]] == [
        "receive",
        "route",
        "retrieve",
        "no_context",
    ]


def test_eval_high_demand_answer_is_grounded_in_trackflow_briefing():
    case = by_name("high-demand answer remains grounded")
    retrieval = next(event for event in case["trace"] if event["node"] == "retrieve")
    assert retrieval["output"]["sources"] == [
        {
            "source_document": "trackflow-sla-delivery.en.md",
            "section": "High-demand dates",
        }
    ]
    assert "Black Friday" in case["answer"]
    assert "40%" in case["answer"]


def test_eval_ticket_status_uses_tool_and_not_rag():
    case = by_name("ticket status routes only to live incident tool")
    nodes = [event["node"] for event in case["trace"]]
    assert nodes == ["receive", "route", "ticket_lookup", "tool_answer"]
    assert "retrieve" not in nodes
    tool = next(event for event in case["trace"] if event["node"] == "ticket_lookup")
    assert tool["output"]["read_only"] is True
    assert tool["output"]["timeout_seconds"] == 4.0


def test_eval_policy_uses_rag_and_not_tool():
    case = by_name("high-demand answer remains grounded")
    nodes = [event["node"] for event in case["trace"]]
    assert "retrieve" in nodes
    assert "ticket_lookup" not in nodes
    assert "inventory_lookup" not in nodes


def test_eval_tool_outage_never_invents_status():
    case = by_name("incident outage produces honest fallback")
    assert "couldn't confirm" in case["answer"]
    assert "open" not in case["answer"]
    assert "resolved" not in case["answer"]
