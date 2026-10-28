"""Compiled LangGraph for TrackFlow's grounded support assistant."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from trackflow_pipeline.rag import NO_INFORMATION, generate_answer, retrieve

from .memory import MemoryStore, classify_decision, evaluate_memory_candidate
from .tools import (
    IncidentReader,
    InventoryLookupInput,
    InventoryReader,
    TicketLookupInput,
    lookup_inventory,
    lookup_ticket,
)
from .traces import TraceStore

Retriever = Callable[[str], list[dict[str, Any]]]
Generator = Callable[[str, list[dict[str, Any]]], str]


class AgentState(TypedDict, total=False):
    """Only data required by the next node; conversation history is excluded."""

    run_id: str
    user_id: str
    question: str
    context: list[dict[str, Any]]
    tool_context: list[dict[str, Any]]
    route: str
    ticket_id: int
    needs_inventory: bool
    needs_rag: bool
    answer: str
    error: str
    memory_decision_only: bool
    memory_decision: str


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    answer: str
    trace: list[dict[str, Any]]


@dataclass(frozen=True)
class AgentRuntime:
    graph: Any
    traces: TraceStore

    def invoke(
        self,
        question: str,
        run_id: str | None = None,
        user_id: str = "anonymous",
    ) -> AgentRun:
        actual_run_id = run_id or str(uuid4())
        final = self.graph.invoke(
            {"question": question, "run_id": actual_run_id, "user_id": user_id},
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
    incident_reader: IncidentReader | None = None,
    inventory_reader: InventoryReader | None = None,
    memory_store: MemoryStore | None = None,
) -> AgentRuntime:
    """Define and compile the graph before any request can execute it."""
    traces = trace_store or TraceStore()
    memories = memory_store

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

    def memory_decision_node(state: AgentState) -> AgentState:
        """Resolve exactly one prior proposal before handling this turn."""
        if memories is None:
            traces.append(state["run_id"], "memory_decision", {"pending": False})
            return {"memory_decision_only": False}
        proposal = memories.pending(state["user_id"])
        if proposal is None:
            traces.append(state["run_id"], "memory_decision", {"pending": False})
            return {"memory_decision_only": False}

        decision = classify_decision(state["question"])
        saved = memories.resolve(proposal, decision, state["question"])
        traces.append(
            state["run_id"],
            "memory_decision",
            {
                "pending": True,
                "proposal_id": proposal.proposal_id,
                "decision": decision.label,
                "persisted": saved is not None,
            },
        )
        if decision.label in {"approve", "edit"} and saved:
            confirmation = "I saved that approved TrackFlow memory."
        elif decision.label == "ambiguous":
            confirmation = "I did not save it because the response was not an explicit approval."
        else:
            confirmation = "I did not save that proposed memory."
        if decision.remaining_message:
            return {
                "question": decision.remaining_message,
                "memory_decision_only": False,
                "memory_decision": confirmation,
            }
        return {
            "answer": confirmation,
            "memory_decision_only": True,
            "memory_decision": confirmation,
        }

    def memory_lookup_node(state: AgentState) -> AgentState:
        records = memories.search(state["user_id"], state["question"]) if memories else []
        context = [
            {
                "source_document": "trackflow-agent-memory",
                "section": f"{record.category}:{record.scope_key}",
                "text": record.fact,
            }
            for record in records
        ]
        traces.append(
            state["run_id"],
            "memory_lookup",
            {
                "match_count": len(records),
                "categories": sorted({record.category for record in records}),
            },
        )
        return {"tool_context": context}

    def route_node(state: AgentState) -> AgentState:
        question = state["question"]
        lowered = question.lower()
        incident_signal = any(word in lowered for word in ("incident", "ticket", "case"))
        inventory_signal = any(
            word in lowered for word in ("inventory", "stock", "sku", "units available")
        )
        knowledge_signal = any(
            phrase in lowered
            for phrase in (
                "policy",
                "procedure",
                "rule",
                "guidance",
                "how should",
                "what should",
                "process for",
            )
        )
        ticket_match = re.search(
            r"(?:incident|ticket|case)\s*(?:id|number|#|no\.)?\s*[:#-]?\s*(\d+)",
            lowered,
        )
        ticket_id = int(ticket_match.group(1)) if ticket_match else 0
        route = "rag"
        if incident_signal:
            route = "incident"
        elif inventory_signal:
            route = "inventory"
        needs_rag = knowledge_signal or not (incident_signal or inventory_signal)
        output: AgentState = {
            "route": route,
            "ticket_id": ticket_id,
            "needs_inventory": inventory_signal,
            "needs_rag": needs_rag,
        }
        traces.append(
            state["run_id"],
            "route",
            {
                "primary_source": route,
                "needs_rag": needs_rag,
                "needs_inventory": inventory_signal,
                "has_ticket_id": bool(ticket_id),
            },
        )
        return output

    def incident_tool_node(state: AgentState) -> AgentState:
        ticket_id = state.get("ticket_id", 0)
        if not ticket_id:
            result = None
            error = "missing_ticket_id"
            context: list[dict[str, Any]] = []
        else:
            result = lookup_ticket(TicketLookupInput(ticket_id), incident_reader)
            error = result.error
            context = [result.as_context()] if result.found else []
        traces.append(
            state["run_id"],
            "ticket_lookup",
            {
                "ticket_id": ticket_id or None,
                "found": bool(result and result.found),
                "status": result.status if result and result.found else None,
                "error": error,
                "timeout_seconds": 4.0,
                "read_only": True,
            },
        )
        return {"tool_context": [*state.get("tool_context", []), *context], "error": error or ""}

    def inventory_tool_node(state: AgentState) -> AgentState:
        result = lookup_inventory(InventoryLookupInput(state["question"]), inventory_reader)
        context = result.as_context()
        traces.append(
            state["run_id"],
            "inventory_lookup",
            {
                "match_count": len(result.products),
                "skus": [product.sku for product in result.products],
                "error": result.error,
                "timeout_seconds": 4.0,
                "read_only": True,
            },
        )
        return {
            "tool_context": [*state.get("tool_context", []), *context],
            "error": result.error or "",
        }

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
        combined_context = [*state.get("tool_context", []), *state.get("context", [])]
        answer = generator(state["question"], combined_context)
        traces.append(state["run_id"], "generate", {"answer": answer})
        if state.get("memory_decision"):
            answer = f"{state['memory_decision']} {answer}"
        return {"answer": answer}

    def tool_answer_node(state: AgentState) -> AgentState:
        context = state.get("tool_context", [])
        if context:
            answer = " ".join(str(item["text"]) for item in context)
        elif state.get("route") == "incident":
            if state.get("ticket_id"):
                answer = (
                    f"I couldn't confirm incident {state['ticket_id']}'s status right now. "
                    "Please try again shortly."
                )
            else:
                answer = "Please include the incident or ticket number you want me to check."
        else:
            answer = (
                "I couldn't confirm current inventory from the live inventory manager "
                "right now. Please try again shortly."
            )
        traces.append(
            state["run_id"],
            "tool_answer",
            {"answer": answer, "used_live_context": bool(context)},
        )
        if state.get("memory_decision"):
            answer = f"{state['memory_decision']} {answer}"
        return {"answer": answer}

    def invalid_question_node(state: AgentState) -> AgentState:
        answer = "Please provide a TrackFlow policy question."
        traces.append(state["run_id"], "invalid_question", {"answer": answer})
        return {"answer": answer}

    def no_context_node(state: AgentState) -> AgentState:
        answer = NO_INFORMATION
        if state.get("memory_decision"):
            answer = f"{state['memory_decision']} {answer}"
        traces.append(state["run_id"], "no_context", {"answer": answer})
        return {"answer": answer}

    def memory_review_node(state: AgentState) -> AgentState:
        """Evaluate after answering and request consent; never write here."""
        answer = state.get("answer", NO_INFORMATION)
        candidate = evaluate_memory_candidate(state["question"])
        proposed = False
        proposal_id = None
        if memories and candidate and memories.pending(state["user_id"]) is None:
            proposal = memories.propose(
                user_id=state["user_id"],
                run_id=state["run_id"],
                originating_message=state["question"],
                candidate=candidate,
            )
            proposal_id = proposal.proposal_id
            proposed = True
            answer = (
                f"{answer}\n\nThis may help with future TrackFlow work: "
                f"{candidate.fact}\nWould you like me to remember it? "
                "Reply exactly with approve, reject, or edit: <corrected fact>."
            )
        traces.append(
            state["run_id"],
            "memory_review",
            {
                "candidate": candidate.category if candidate else None,
                "proposed": proposed,
                "proposal_id": proposal_id,
                "persisted": False,
            },
        )
        return {"answer": answer}

    def after_receive(state: AgentState) -> str:
        if state.get("error"):
            return "invalid_question"
        return "memory_decision" if memories else "route"

    def after_memory_decision(state: AgentState) -> str:
        return END if state.get("memory_decision_only") else "memory_lookup"

    def after_route(state: AgentState) -> str:
        if state.get("route") == "incident":
            return "ticket_lookup"
        if state.get("needs_inventory"):
            return "inventory_lookup"
        return "retrieve"

    def after_ticket(state: AgentState) -> str:
        if state.get("needs_inventory"):
            return "inventory_lookup"
        return "retrieve" if state.get("needs_rag") else "tool_answer"

    def after_inventory(state: AgentState) -> str:
        return "retrieve" if state.get("needs_rag") else "tool_answer"

    def after_retrieve(state: AgentState) -> str:
        if state.get("context") or state.get("tool_context"):
            return "generate"
        return "no_context"

    workflow = StateGraph(AgentState)
    workflow.add_node("receive", receive_node)
    workflow.add_node("memory_decision", memory_decision_node)
    workflow.add_node("memory_lookup", memory_lookup_node)
    workflow.add_node("route", route_node)
    workflow.add_node("ticket_lookup", incident_tool_node)
    workflow.add_node("inventory_lookup", inventory_tool_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("tool_answer", tool_answer_node)
    workflow.add_node("invalid_question", invalid_question_node)
    workflow.add_node("no_context", no_context_node)
    workflow.add_node("memory_review", memory_review_node)
    workflow.add_edge(START, "receive")
    workflow.add_conditional_edges(
        "receive",
        after_receive,
        {
            "memory_decision": "memory_decision",
            "route": "route",
            "invalid_question": "invalid_question",
        },
    )
    workflow.add_conditional_edges(
        "memory_decision",
        after_memory_decision,
        {"memory_lookup": "memory_lookup", END: END},
    )
    workflow.add_edge("memory_lookup", "route")
    workflow.add_conditional_edges(
        "route",
        after_route,
        {
            "ticket_lookup": "ticket_lookup",
            "inventory_lookup": "inventory_lookup",
            "retrieve": "retrieve",
        },
    )
    workflow.add_conditional_edges(
        "ticket_lookup",
        after_ticket,
        {
            "inventory_lookup": "inventory_lookup",
            "retrieve": "retrieve",
            "tool_answer": "tool_answer",
        },
    )
    workflow.add_conditional_edges(
        "inventory_lookup",
        after_inventory,
        {"retrieve": "retrieve", "tool_answer": "tool_answer"},
    )
    workflow.add_conditional_edges(
        "retrieve",
        after_retrieve,
        {"generate": "generate", "no_context": "no_context"},
    )
    workflow.add_edge("generate", "memory_review" if memories else END)
    workflow.add_edge("tool_answer", "memory_review" if memories else END)
    workflow.add_edge("invalid_question", END)
    workflow.add_edge("no_context", "memory_review" if memories else END)
    workflow.add_edge("memory_review", END)

    # Compilation validates the state machine before requests reach it.
    compiled = workflow.compile(checkpointer=MemorySaver())
    return AgentRuntime(graph=compiled, traces=traces)
