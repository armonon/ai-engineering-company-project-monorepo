# TrackFlow RAG design

## Purpose and scope

The knowledge assistant gives authenticated backoffice staff grounded answers
about four approved sales-policy documents: delivery SLA, returns, carrier
coverage, and storage pricing. It is deliberately not a general chatbot. When
retrieval does not provide evidence, the generation prompt requires the exact
honesty response: `I don't have enough verified TrackFlow information to answer that.`

## Data flow

```text
approved Markdown -> semantic paragraph chunks -> dedicated embedding model
       -> trackflow_knowledge (Qdrant, cosine similarity)

staff question -> same embedding model -> top-5 retrieval (score >= 0.55)
       -> strict policy prompt + retrieved context -> distinct chat model
       -> POST /knowledge/query -> authenticated backoffice answer
```

`data/process/rag.py` owns loading, chunking, embedding, and idempotent setup.
`data/pipelines/rag.py` owns `retrieve`, `generate_answer`, and `query`. The API
router contains no retrieval logic. The backoffice uses its existing central
authenticated fetch layer, so bearer-token and readable-error behaviour are
consistent with the rest of the application.

## Chunking and payload contract

Paragraph boundaries are semantic boundaries in these short policy documents.
Lists stay together as a single semantic unit so a carrier or pricing rule is
not separated from its conditions. The collection contains 18 chunks, at
least three from each source. Every point has exactly these payload fields:

- `company`
- `source_document`
- `section`
- `language`
- `chunk_index`
- `text`

Point IDs are deterministic UUIDv5 values derived from source filename and
chunk index. Setup clears and recreates the collection by default, then upserts
the known IDs. Rerunning setup therefore cannot create duplicates.

## Models and vector store

Production uses the OpenAI-compatible 4Geeks LiteLLM gateway:

- Embeddings: `downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b`
- Generation: `downtown-miami/groq/llama-3.1-8b-instant`
- Qdrant collection: `trackflow_knowledge`
- Distance: cosine
- Retrieval: top 5, minimum score `0.55`

The loader detects the embedding vector size from the provider's first result
and rejects inconsistent dimensions. Code also rejects configuration that uses
the same model ID for embedding and generation. Credentials live only in
ignored `.env` files; the committed examples contain names and empty values.

## Grounding and business safeguards

The system prompt permits answers only from retrieved context and explicitly
forbids invented prices, deadlines, coverage, approvals, or exceptions. It
also restates the three highest-risk rules:

1. Never promise an SLA during declared Black Friday, Christmas, or January Sales.
2. International returns require manual handling by Sofía Ramos's team.
3. Preferential storage pricing requires Miguel Torres's approval.

Retrieved content is labelled as evidence, not instructions, to reduce prompt
injection risk. The endpoint returns only `{ "answer": "..." }`; it does not
expose raw chunks, prompts, provider errors, keys, or internal model metadata.

## Evaluation and verification

`data/eval/rag-test-queries.json` contains twelve questions covering all four
documents, including high-demand delivery dates. `data/eval/evaluate_rag.py`
loads an in-memory Qdrant collection and calls the production `setup` and
`retrieve` functions. Because CI cannot contain a private LiteLLM key, that
script injects a deterministic local TF-IDF encoder solely for reproducible
retrieval evidence. Runtime remains configured for the dedicated 4Geeks
embedding API. The generated `rag-evaluation.json` records every top-three
source result and must report Recall@3 of at least 80%.

Unit tests mock provider boundaries and verify metadata, idempotency, score
filtering, the retrieve-then-generate contract, empty-context honesty, API auth,
safe service errors, and the backoffice bearer-token request.

## Limitations and operating procedure

- The four Markdown files are the complete authority. New policies are unknown
  until reviewed, added, and the collection is reloaded.
- Similarity thresholds require re-evaluation after changing the embedding
  model or documents.
- A successful retrieval does not replace human approval where policy names an
  approver.
- Start Qdrant, configure a valid LiteLLM virtual key, then run
  `python scripts/setup_rag.py` before serving real questions.
- Provider and Qdrant outages produce a safe HTTP 503 and a readable UI error;
  the system does not fall back to an ungrounded answer.
