from __future__ import annotations

from pathlib import Path

from trackflow_agent import TraceStore, build_graph
from trackflow_pipeline.rag import NO_INFORMATION


def runtime(tmp_path: Path, context: list[dict] | None = None):
    retrieved = [] if context is None else context
    return build_graph(
        retriever=lambda _question: retrieved,
        generator=lambda _question, _context: "grounded answer",
        trace_store=TraceStore(tmp_path / "traces.db"),
    )


def test_empty_question_routes_to_clear_error_without_retrieval(tmp_path: Path):
    calls = []
    graph = build_graph(
        retriever=lambda question: calls.append(question) or [],
        generator=lambda _question, _context: "should not run",
        trace_store=TraceStore(tmp_path / "empty.db"),
    )
    result = graph.invoke("   ", run_id="empty-run")
    assert result.answer == "Please provide a TrackFlow policy question."
    assert [event["node"] for event in result.trace] == ["receive", "invalid_question"]
    assert calls == []


def test_no_context_routes_to_honest_answer_without_generation(tmp_path: Path):
    generation_calls = []
    graph = build_graph(
        retriever=lambda _question: [],
        generator=lambda *args: generation_calls.append(args) or "unsafe",
        trace_store=TraceStore(tmp_path / "no-context.db"),
    )
    result = graph.invoke("Unknown policy", run_id="unknown-run")
    assert result.answer == NO_INFORMATION
    assert [event["node"] for event in result.trace] == ["receive", "retrieve", "no_context"]
    assert generation_calls == []


def test_retrieval_and_generation_are_separate_single_calls(tmp_path: Path):
    context = [{"source_document": "policy.md", "section": "SLA", "text": "40%"}]
    calls = []

    def retrieve_once(question):
        calls.append(("retrieve", question))
        return context

    def generate_once(question, received_context):
        calls.append(("generate", question, received_context))
        return "Delivery may take 40% longer."

    graph = build_graph(
        retriever=retrieve_once,
        generator=generate_once,
        trace_store=TraceStore(tmp_path / "grounded.db"),
    )
    result = graph.invoke("Black Friday?", run_id="grounded-run")
    assert result.answer == "Delivery may take 40% longer."
    assert calls == [
        ("retrieve", "Black Friday?"),
        ("generate", "Black Friday?", context),
    ]
    assert [event["node"] for event in result.trace] == ["receive", "retrieve", "generate"]


def test_checkpoint_contains_final_state(tmp_path: Path):
    graph = runtime(tmp_path, [{"text": "approved context"}])
    graph.invoke("What is approved?", run_id="checkpoint-run")
    snapshot = graph.graph.get_state({"configurable": {"thread_id": "checkpoint-run"}})
    assert snapshot.values["answer"] == "grounded answer"
    assert snapshot.values["context"] == [{"text": "approved context"}]
