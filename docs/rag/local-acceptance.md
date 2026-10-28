# RAG local acceptance evidence

Date: 2026-10-28

The complete runtime path was exercised locally with an in-memory Qdrant
instance and two distinct local OpenAI-compatible models:

- Embedding: `nomic-embed-text` through Ollama (768 dimensions)
- Generation: `qwen2.5:7b` through Ollama
- Collection: `trackflow_knowledge`
- Loaded points: 18

Question:

> Can we promise express delivery during Black Friday?

Retrieved first: `trackflow-sla-delivery.en.md`, section `High-demand dates`.

Generated answer:

> No explicit SLA can be promised during declared high-demand dates like Black
> Friday. Delivery times may extend by up to an additional 40%, and this must be
> communicated proactively to clients in advance.

This local run verifies real embedding, vector retrieval, grounding, and
generation without placing a provider credential in source control. Production
remains configured for the two distinct 4Geeks LiteLLM model IDs documented in
`rag-design.md`.
