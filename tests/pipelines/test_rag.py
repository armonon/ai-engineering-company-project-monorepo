from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from qdrant_client import QdrantClient
from trackflow_pipeline import rag as pipeline
from trackflow_process.rag import COLLECTION_NAME, SECTION_NAMES, chunk_documents, setup

ROOT = Path(__file__).resolve().parents[2]


def semantic_stub(text: str) -> list[float]:
    """Small deterministic vectors for unit testing collection mechanics."""
    value = sum(text.encode("utf-8"))
    return [float(value % 97), float((value // 97) % 89), 1.0]


def test_company_documents_produce_required_metadata_and_three_or_more_chunks():
    chunks = chunk_documents(ROOT / "docs" / "company-knowledge-base")
    assert len(chunks) == 18
    for source in SECTION_NAMES:
        matching = [chunk for chunk in chunks if chunk["source_document"] == source]
        assert len(matching) >= 3
        assert [chunk["chunk_index"] for chunk in matching] == list(range(len(matching)))
        assert all(
            set(chunk)
            == {"company", "source_document", "section", "language", "chunk_index", "text"}
            for chunk in matching
        )


def test_setup_is_idempotent_and_uses_exact_collection_name():
    client = QdrantClient(":memory:")
    first = setup(client, semantic_stub, ROOT / "docs" / "company-knowledge-base")
    second = setup(client, semantic_stub, ROOT / "docs" / "company-knowledge-base")
    assert first == second == {"collection": COLLECTION_NAME, "chunks": 18, "dimensions": 3}
    assert client.count(COLLECTION_NAME, exact=True).count == 18


@dataclass
class Point:
    payload: dict
    score: float


class RetrievalClient:
    def query_points(self, **kwargs):
        assert kwargs["collection_name"] == COLLECTION_NAME
        assert kwargs["limit"] == 3
        assert kwargs["score_threshold"] == 0.7
        return SimpleNamespace(points=[Point({"text": "grounded"}, 0.91)])


def test_retrieve_returns_only_payloads_and_can_return_fewer_than_k():
    result = pipeline.retrieve(
        "question", k=3, min_score=0.7, client=RetrievalClient(), embedding_fn=semantic_stub
    )
    assert result == [{"text": "grounded"}]


def test_generate_answer_uses_context_and_distinct_generation_model(monkeypatch):
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="No SLA guarantee."))]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setenv("EMBEDDING_MODEL", "embed-model")
    answer = pipeline.generate_answer(
        "Black Friday?",
        [{"source_document": "sla.md", "section": "Peaks", "text": "No guarantee."}],
        client=client,
        model="generation-model",
    )
    assert answer == "No SLA guarantee."
    assert captured["model"] == "generation-model"
    assert "No guarantee" in captured["messages"][1]["content"]
    assert captured["temperature"] == 0


def test_empty_context_still_uses_generator_with_honesty_instruction(monkeypatch):
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=pipeline.NO_INFORMATION))]
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setenv("EMBEDDING_MODEL", "embed-model")
    assert (
        pipeline.generate_answer("Unknown?", [], client=client, model="chat-model")
        == pipeline.NO_INFORMATION
    )
    assert pipeline.NO_INFORMATION in captured["messages"][0]["content"]


def test_query_is_retrieve_then_generate(monkeypatch):
    calls = []
    monkeypatch.setattr(
        pipeline,
        "retrieve",
        lambda question: calls.append(("retrieve", question)) or [{"text": "evidence"}],
    )
    monkeypatch.setattr(
        pipeline,
        "generate_answer",
        lambda question, context: calls.append(("generate", question, context)) or "answer",
    )
    assert pipeline.query("policy?") == "answer"
    assert calls == [("retrieve", "policy?"), ("generate", "policy?", [{"text": "evidence"}])]
