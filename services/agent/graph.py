"""Compiled LangGraph for TrackFlow's grounded support assistant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from trackflow_pipeline.rag import NO_INFORMATION, generate_answer, retrieve

from .traces import TraceStore

Retriever = Callable[[str], list[dict[str, Any]]]
Generator = Callable[[str, list[dict[str, Any]]], str]


class AgentState(TypedDict, total=False):
    """Only data required by the next node; conversation history is excluded."""

    run_id: str
    question: str
    context: list[dict[str, Any]]
    answer: str
    error: str


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    answer: str
    trace: list[dict[str, Any]]


@dataclass(frozen=True)
class AgentRuntime:
    graph: Any
    traces: TraceStore

    def invoke(self, question: str, run_id: str | None = None) -> AgentRun:
        actual_run_id = run_id or str(uuid4())
        final = self.graph.invoke(
            {"question": question, "run_id": actual_run_id},
            config={"configurable": {"thread_id": actual_run_id}},
        )
        return AgentRun(
            run_id=actual_run_id,
            answer=str(final.get("answer", NO_INFORMATION)),
            trace=self.traces.get(actual_run_id),
        )


def build_graph(
    retriever: Retriever = retrieve,
    generator: Generator = generate_answer,
    trace_store: TraceStore | None = None,
) -> AgentRuntime:
    """Define and compile the graph before any request can execute it."""
    traces = trace_store or TraceStore()

    def receive_node(state: AgentState) -> AgentState:
        question = str(state.get("question", "")).strip()
        run_id = state["run_id"]
        output: AgentState = {"question": question}
        safe_output: dict[str, Any] = {"question_length": len(question)}
        if not question:
            output["error"] = "empty_question"
            safe_output["error"] = "empty_question"
        traces.append(run_id, "receive", safe_output)
        return output

    def retrieve_node(state: AgentState) -> AgentState:
        context = retriever(state["question"])
        traces.append(
            state["run_id"],
            "retrieve",
            {
                "context_count": len(context),
                "sources": [
                    {
                        "source_document": item.get("source_document"),
                        "section": item.get("section"),
                    }
                    for item in context
                ],
            },
        )
        return {"context": context}

    def generate_node(state: AgentState) -> AgentState:
        answer = generator(state["question"], state["context"])
        traces.append(state["run_id"], "generate", {"answer": answer})
        return {"answer": answer}

    def invalid_question_node(state: AgentState) -> AgentState:
        answer = "Please provide a TrackFlow policy question."
        traces.append(state["run_id"], "invalid_question", {"answer": answer})
        return {"answer": answer}

    def no_context_node(state: AgentState) -> AgentState:
        traces.append(state["run_id"], "no_context", {"answer": NO_INFORMATION})
        return {"answer": NO_INFORMATION}

    def after_receive(state: AgentState) -> str:
        return "invalid_question" if state.get("error") else "retrieve"

    def after_retrieve(state: AgentState) -> str:
        return "generate" if state.get("context") else "no_context"

    workflow = StateGraph(AgentState)
    workflow.add_node("receive", receive_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("invalid_question", invalid_question_node)
    workflow.add_node("no_context", no_context_node)
    workflow.add_edge(START, "receive")
    workflow.add_conditional_edges(
        "receive",
        after_receive,
        {"retrieve": "retrieve", "invalid_question": "invalid_question"},
    )
    workflow.add_conditional_edges(
        "retrieve",
        after_retrieve,
        {"generate": "generate", "no_context": "no_context"},
    )
    workflow.add_edge("generate", END)
    workflow.add_edge("invalid_question", END)
    workflow.add_edge("no_context", END)

    # Compilation validates the state machine before requests reach it.
    compiled = workflow.compile(checkpointer=MemorySaver())
    return AgentRuntime(graph=compiled, traces=traces)
