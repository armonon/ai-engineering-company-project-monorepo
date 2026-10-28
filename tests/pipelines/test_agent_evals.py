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
