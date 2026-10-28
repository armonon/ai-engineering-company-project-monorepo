"""TrackFlow knowledge-base ingestion and embedding utilities.

The source documents are deliberately small policy documents.  Paragraph-level
semantic chunks preserve complete business rules (especially exceptions) while
remaining narrow enough for precise retrieval.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

COLLECTION_NAME = "trackflow_knowledge"
PRODUCTION_BASE_URL = "https://llm.4geeks.ai/v1"
DEFAULT_EMBEDDING_MODEL = "downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b"
DEFAULT_GENERATION_MODEL = "downtown-miami/groq/llama-3.1-8b-instant"
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"

SECTION_NAMES = {
    "trackflow-sla-delivery.en.md": [
        "Service scope",
        "Delivery windows",
        "Monthly SLA and compensation",
        "High-demand dates",
    ],
    "trackflow-returns-policy.en.md": [
        "Reverse logistics overview",
        "Reverse logistics process",
        "Return window",
        "Return costs",
        "International returns",
        "Service boundary",
    ],
    "trackflow-carrier-coverage.en.md": [
        "Network overview",
        "United States coverage",
        "Spain coverage",
        "Carrier-selection exceptions",
    ],
    "trackflow-storage-pricing.en.md": [
        "Billing basis",
        "Rates and aging charges",
        "Aging reports",
        "Discount approval",
    ],
}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_documents(knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR) -> list[dict]:
    """Return deterministic, policy-complete chunks and their required metadata."""
    root = Path(knowledge_dir)
    chunks: list[dict] = []
    for filename, section_names in SECTION_NAMES.items():
        source = root / filename
        if not source.exists():
            raise FileNotFoundError(f"Required knowledge document is missing: {source}")
        raw = source.read_text(encoding="utf-8").strip()
        title, *paragraphs = re.split(r"\n\s*\n", raw)
        clean_paragraphs = [_normalise(value) for value in paragraphs if _normalise(value)]
        if len(clean_paragraphs) != len(section_names):
            raise ValueError(
                f"{filename} produced {len(clean_paragraphs)} chunks; "
                f"the approved design requires {len(section_names)}."
            )
        document_title = title.removeprefix("# ").strip()
        for index, (section, paragraph) in enumerate(
            zip(section_names, clean_paragraphs, strict=True)
        ):
            chunks.append(
                {
                    "company": "TrackFlow",
                    "source_document": filename,
                    "section": section,
                    "language": "en",
                    "chunk_index": index,
                    "text": f"{document_title} — {section}: {paragraph}",
                }
            )
    return chunks


def _provider_client() -> OpenAI:
    api_key = os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("LITELLM_API_KEY is required to embed the knowledge base.")
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("LITELLM_BASE_URL", PRODUCTION_BASE_URL),
    )


def embed(text: str, client: OpenAI | None = None, model: str | None = None) -> list[float]:
    """Embed one string with the dedicated embedding model."""
    embedding_model = model or os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    generation_model = os.getenv("GENERATION_MODEL", DEFAULT_GENERATION_MODEL)
    if embedding_model == generation_model:
        raise ValueError("Embedding and generation must use different model IDs.")
    response = (client or _provider_client()).embeddings.create(
        model=embedding_model,
        input=text,
    )
    return [float(value) for value in response.data[0].embedding]


def qdrant_client() -> QdrantClient:
    return QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))


def setup(
    client: QdrantClient | None = None,
    embedding_fn: Callable[[str], list[float]] = embed,
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    recreate: bool = True,
) -> dict[str, int | str]:
    """Create and load the collection; repeated runs cannot duplicate points."""
    qdrant = client or qdrant_client()
    chunks = chunk_documents(knowledge_dir)
    vectors = [embedding_fn(chunk["text"]) for chunk in chunks]
    if not vectors or not vectors[0]:
        raise ValueError("The embedding provider returned an empty vector.")
    dimensions = len(vectors[0])
    if any(len(vector) != dimensions for vector in vectors):
        raise ValueError("The embedding provider returned inconsistent vector dimensions.")

    if recreate and qdrant.collection_exists(COLLECTION_NAME):
        qdrant.delete_collection(COLLECTION_NAME)
    if not qdrant.collection_exists(COLLECTION_NAME):
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"trackflow:{chunk['source_document']}:{chunk['chunk_index']}",
                )
            ),
            vector=vector,
            payload=chunk,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    qdrant.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    return {"collection": COLLECTION_NAME, "chunks": len(points), "dimensions": dimensions}
