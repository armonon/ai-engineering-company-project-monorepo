"""Reproducible offline Recall@3 evidence using the production Qdrant path.

Runtime uses the configured LiteLLM embedding model.  CI cannot hold a private
provider key, so this evidence substitutes a fitted local TF-IDF encoder while
calling the same ``setup`` and ``retrieve`` functions and the same Qdrant API.
"""

from __future__ import annotations

import json
from pathlib import Path

from qdrant_client import QdrantClient
from sklearn.feature_extraction.text import TfidfVectorizer
from trackflow_pipeline.rag import retrieve
from trackflow_process.rag import chunk_documents, setup

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    knowledge_dir = ROOT / "docs" / "company-knowledge-base"
    query_path = ROOT / "data" / "eval" / "rag-test-queries.json"
    output_path = ROOT / "data" / "eval" / "rag-evaluation.json"
    queries = json.loads(query_path.read_text(encoding="utf-8"))
    chunks = chunk_documents(knowledge_dir)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=2048,
        sublinear_tf=True,
    )
    vectorizer.fit([chunk["text"] for chunk in chunks] + [row["question"] for row in queries])

    def local_embedding(text: str) -> list[float]:
        return vectorizer.transform([text]).toarray()[0].astype(float).tolist()

    client = QdrantClient(":memory:")
    setup(client, local_embedding, knowledge_dir)
    results = []
    hits = 0
    for row in queries:
        retrieved = retrieve(
            row["question"], k=3, min_score=0.0, client=client, embedding_fn=local_embedding
        )
        sources = [item["source_document"] for item in retrieved]
        hit = row["source_document"] in sources
        hits += int(hit)
        results.append({**row, "retrieved_sources": sources, "hit_at_3": hit})

    recall = hits / len(queries)
    report = {
        "metric": "Recall@3",
        "query_count": len(queries),
        "hits": hits,
        "recall_at_3": round(recall, 4),
        "required_minimum": 0.8,
        "passed": recall >= 0.8,
        "evaluation_encoder": "offline TF-IDF char n-gram substitute (CI evidence only)",
        "runtime_embedding_model": "downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b",
        "results": results,
    }
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Recall@3: {hits}/{len(queries)} = {recall:.1%}")
    return 0 if recall >= 0.8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
