# AI Engineering course study guide — TrackFlow

## 1. Implementing data pipelines

Design extract/transform/load work as small, observable steps. Make loads
idempotent so retries do not duplicate business records; cache only pure work;
record run metadata and expose operational status. In TrackFlow, Prefect
orchestrates weekly warehouse/client KPIs and writes reporting rows with
conflict-safe upserts.

**Assessment answer:** reliability comes from retries, idempotency, validation,
and traceable runs—not merely from scheduling a script.

## 2. Asynchronous processing and offloading

Move slow or failure-prone work out of the request-response path. A broker
accepts jobs, independent workers execute them, retry policy handles transient
failure, and terminal failures remain inspectable. TrackFlow uses Celery and
Redis, with Flower for operational visibility.

**Assessment answer:** return quickly from the API, pass small serializable job
payloads, make tasks idempotent, and distinguish retryable from permanent
errors.

## 3. Models training and RAG

Split before fitting, keep preprocessing inside the pipeline, select metrics by
business cost, tune with cross-validation, inspect variance, and reserve the
test set for final confirmation. For RAG, retrieval and generation are separate:
chunk approved evidence, embed it, retrieve with a threshold, and refuse when
evidence is inadequate.

**Assessment answer:** a high score is not enough; prove that evaluation is
leakage-free, stable, tied to the business objective, and reproducible.

## 4. Agentic engineering

An agent combines a model with state, tools, and an explicit decision boundary.
Typed tools reduce ambiguity; MCP standardizes tool exposure; routing chooses
which capability runs; memory should be scoped, reviewable, and never treated as
trusted policy by default.

**Assessment answer:** tools expand capability, but schemas, least privilege,
tenant checks, and traces keep that capability controlled.

## 5. Agentic workflows

Use a graph when work has stages, branches, approvals, retries, or resumability.
Checkpoint state at meaningful transitions. Human-in-the-loop is a modeled
state—not an improvised pause—and independent branches should not block one
another unnecessarily.

**Assessment answer:** deterministic orchestration surrounds probabilistic model
steps, making long-running work testable and recoverable.

## 6. Real-time communication

Use server-sent events for ordered server-to-browser progress and WebSockets for
bidirectional controls. Persist events for replay, authenticate control actors,
make transitions atomic, and distinguish resumable pause from terminal cancel.

**Assessment answer:** real time is a state-consistency problem as much as a
transport choice; clients must reconnect and recover the authoritative state.

## 7. Secure AI applications

Treat prompts, retrieved documents, model output, and tool responses as
untrusted data. Separate system instructions from user input, allowlist tool
properties, rate-limit model endpoints, redact secrets/PII, test direct and
indirect injection, and audit conventional OWASP risks alongside AI-specific
ones.

**Assessment answer:** prompt wording is not a security boundary. Enforce
authorization and validation in code at every data and tool boundary.

## 8. AI engineering project delivery

Pitch the business result, demonstrate one coherent workflow, explain a real
trade-off, and show how success and failure are measured. Package durable links
and evidence so another person can evaluate the system without the developer
present.

**Assessment answer:** delivery proves that the system runs, creates business
value, is understandable to operators, and can be handed off responsibly.

## One-sentence architecture summary

TrackFlow combines transactional operations, idempotent pipelines, asynchronous
workers, evidence-only RAG, checkpointed agent graphs, real-time observability,
human approvals, and defense-in-depth security in one company monorepo.
