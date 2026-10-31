from __future__ import annotations

import time
from pathlib import Path

from trackflow_agent import MemoryStore, TicketLookupInput, TraceStore, build_graph
from trackflow_agent.tools import lookup_ticket
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
    assert [event["node"] for event in result.trace] == [
        "receive",
        "input_guard",
        "route",
        "retrieve",
        "no_context",
        "output_guard",
    ]
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
    assert calls[0] == ("retrieve", "Black Friday?")
    assert calls[1][0:2] == ("generate", "Black Friday?")
    assert calls[1][2][0]["source_document"] == "policy.md"
    assert "UNTRUSTED_EVIDENCE" in calls[1][2][0]["text"]
    assert [event["node"] for event in result.trace] == [
        "receive",
        "input_guard",
        "route",
        "retrieve",
        "generate",
        "output_guard",
    ]


def test_checkpoint_contains_final_state(tmp_path: Path):
    graph = runtime(tmp_path, [{"text": "approved context"}])
    graph.invoke("What TrackFlow policy is approved?", run_id="checkpoint-run")
    snapshot = graph.graph.get_state({"configurable": {"thread_id": "checkpoint-run"}})
    assert snapshot.values["answer"] == "grounded answer"
    assert snapshot.values["context"] == [{"text": "approved context"}]


def test_ticket_question_uses_real_reader_not_rag(tmp_path: Path):
    rag_calls = []
    graph = build_graph(
        retriever=lambda question: rag_calls.append(question) or [],
        generator=lambda *_args: "should not run",
        incident_reader=lambda ticket_id: {
            "id": ticket_id,
            "status": "in_progress",
            "category": "delivery_delay",
            "origin": "customer",
            "branch": "los_angeles",
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": "2026-10-02T00:00:00Z",
        },
        trace_store=TraceStore(tmp_path / "ticket.db"),
    )
    result = graph.invoke("What is the status of ticket 482?", run_id="ticket-run")
    assert (
        "Incident 482 is in progress. Category: delivery delay. "
        "Handled by the Los Angeles office. Last updated 02 Oct 2026."
    ) in result.answer
    assert [event["node"] for event in result.trace] == [
        "receive",
        "input_guard",
        "route",
        "ticket_lookup",
        "tool_answer",
        "output_guard",
    ]
    assert rag_calls == []


def test_policy_question_uses_rag_not_operational_tools(tmp_path: Path):
    tool_calls = []
    graph = build_graph(
        retriever=lambda _question: [{"text": "Escalate after 24 hours."}],
        generator=lambda _question, _context: "Escalate after 24 hours.",
        incident_reader=lambda ticket_id: tool_calls.append(ticket_id),
        trace_store=TraceStore(tmp_path / "policy.db"),
    )
    result = graph.invoke("What is the escalation policy?", run_id="policy-run")
    assert result.answer == "Escalate after 24 hours."
    assert "ticket_lookup" not in [event["node"] for event in result.trace]
    assert tool_calls == []


def test_incident_tool_timeout_returns_typed_honest_failure():
    def slow_reader(_ticket_id: int):
        time.sleep(0.1)
        return {"status": "open"}

    result = lookup_ticket(TicketLookupInput(ticket_id=482), slow_reader, timeout_seconds=0.01)
    assert result.found is False
    assert result.error == "timeout"
    assert result.status is None


def test_inventory_question_uses_separate_read_only_tool(tmp_path: Path):
    graph = build_graph(
        retriever=lambda _question: [],
        generator=lambda *_args: "should not run",
        inventory_reader=lambda _query: [
            {
                "id": 4,
                "name": "USB-C Fast Charger 65W",
                "sku": "TEC-CHG-065",
                "warehouse": "ZGZ",
                "current_stock": 31,
            }
        ],
        trace_store=TraceStore(tmp_path / "inventory.db"),
    )
    result = graph.invoke("How many TEC-CHG-065 units are in stock?", run_id="inventory-run")
    assert "31 units in warehouse ZGZ" in result.answer
    assert [event["node"] for event in result.trace] == [
        "receive",
        "input_guard",
        "route",
        "inventory_lookup",
        "tool_answer",
        "output_guard",
    ]


def test_memory_requires_a_separate_explicit_approval_turn(tmp_path: Path):
    memory = MemoryStore(tmp_path / "memory.db")
    graph = build_graph(
        retriever=lambda _question: [{"text": "Carrier policy context."}],
        generator=lambda _question, context: " | ".join(item["text"] for item in context),
        trace_store=TraceStore(tmp_path / "memory-traces.db"),
        memory_store=memory,
    )

    first = graph.invoke(
        "SEUR no longer covers rural Zaragoza, so we must use the local carrier.",
        run_id="proposal-run",
        user_id="7",
    )
    assert "Would you like me to remember it?" in first.answer
    assert memory.list_memories("7") == []
    assert memory.pending("7") is not None
    assert first.trace[-1]["node"] == "memory_review"
    assert first.trace[-1]["output"]["persisted"] is False

    second = graph.invoke("Yes, remember it", run_id="approval-run", user_id="7")
    assert second.answer == "I saved that approved TrackFlow memory."
    assert len(memory.list_memories("7")) == 1
    assert second.trace[-1]["output"]["decision"] == "approve"

    third = graph.invoke("What is the SEUR rule for Zaragoza?", run_id="recall-run", user_id="7")
    assert "SEUR no longer covers rural Zaragoza" in third.answer
    lookup = next(event for event in third.trace if event["node"] == "memory_lookup")
    assert lookup["output"]["match_count"] == 1


def test_ambiguous_memory_response_is_logged_as_rejected(tmp_path: Path):
    memory = MemoryStore(tmp_path / "rejected-memory.db")
    graph = build_graph(
        retriever=lambda _question: [],
        generator=lambda *_args: "unused",
        trace_store=TraceStore(tmp_path / "rejected-traces.db"),
        memory_store=memory,
    )
    graph.invoke(
        "This is the third ticket this week: delays in Zaragoza are due to flooding.",
        run_id="proposal-run",
        user_id="8",
    )
    result = graph.invoke("maybe later", run_id="reject-run", user_id="8")

    assert "not an explicit approval" in result.answer
    assert memory.list_memories("8") == []
    assert memory.proposal_log("8")[0]["status"] == "ambiguous_rejected"


def test_agent_answers_a_new_question_after_resolving_prior_proposal(tmp_path: Path):
    memory = MemoryStore(tmp_path / "continuation-memory.db")
    graph = build_graph(
        retriever=lambda _question: [{"text": "Escalate after 24 hours."}],
        generator=lambda _question, context: context[-1]["text"],
        trace_store=TraceStore(tmp_path / "continuation-traces.db"),
        memory_store=memory,
    )
    graph.invoke(
        "SEUR no longer covers rural Zaragoza, so we must use the local carrier.",
        run_id="proposal-run",
        user_id="9",
    )
    result = graph.invoke(
        "Approve and what is the escalation policy?",
        run_id="decision-and-question-run",
        user_id="9",
    )

    assert "I saved that approved TrackFlow memory." in result.answer
    assert "Escalate after 24 hours." in result.answer
    assert [event["node"] for event in result.trace][:3] == [
        "receive",
        "memory_decision",
        "input_guard",
    ]
