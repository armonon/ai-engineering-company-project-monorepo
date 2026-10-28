# TrackFlow AI security review — NIST CSF 2.0

Date: 2026-10-28  
Scope: Los Angeles (US) and Zaragoza (Spain) TrackFlow applications  
Accountable executive: Andrés, CTO

## Regulatory and data context

TrackFlow processes B2C names, contact details, delivery addresses, and order
data, plus confidential B2B contract and volume information. GDPR applies to
the Spain/EU operation; a qualifying personal-data breach must be reported to
the AEPD within 72 hours. CCPA/CPRA applies to California consumers, including
access, deletion, and opt-out rights and prompt breach notification. Customer,
client-brand, carrier-credential, and commercial data must remain tenant- and
purpose-scoped.

## AI system inventory and responsibility

| Component | Owner | Input/model/tool boundary | TrackFlow responsibility | Third-party responsibility |
| --- | --- | --- | --- | --- |
| First-line CX LangGraph agent | Customer Operations | Authenticated chat; LiteLLM model; read-only incident/inventory MCP tools | Authorization, prompt boundary, tool scope, output checks, traces, response handling | Model provider protects hosted inference and reports provider incidents |
| Carrier selection engine | Last Mile Manager (Carlos Mendoza) | Shipment facts and carrier catalogue; deterministic scorer | Validate price/rules; keep recommendation read-only; require dispatch confirmation | Carriers protect API availability and credential use at their edge |
| Return-policy RAG | Compliance & CX (Lucía Fernández) | Uploaded policy chunks; Qdrant; embedding/generation providers | Client/country partitioning, evidence sanitization, retrieval threshold, citations | Qdrant/model hosts protect managed storage/inference infrastructure |
| Returns approval workflow | Reverse Logistics Manager (Sofía Ramos) | Rules, order value, human approval checkpoint | Enforce eligibility; require human confirmation for high-impact approvals | Model provider cannot authorize or execute a return |
| Company-tools MCP server | Platform Engineering | OAuth token and typed read-only tools | Least-privilege scopes, input/output schemas, timeout, audit, deny by default | OIDC provider validates identity lifecycle and token issuance |
| Agent memory | Customer Operations | User-proposed preference/fact store | Explicit approve/edit/reject consent, per-user isolation, no credentials/PII | SQLite/host provider protects storage at rest in production |
| RFP multi-agent workflow | Sales Operations + fixed department owners | PDF/Markdown intake, generators, evaluators, LangGraph checkpoints | Treat documents as untrusted, bounded retries, owner approval before finalization | MarkItDown/model providers protect processing service/runtime |
| Observability and live controls | Platform Engineering | Agent/task traces, SSE, authenticated WebSocket controls | Pseudonymize identity, authorize access, preserve audit, terminal cancel | Hosting provider protects transport and platform logs |

No model is authorized to dispatch shipments, change an in-transit carrier,
approve a high-value return, or disclose one brand's data to another. Those
operations are either unavailable to the agent or require an authenticated
human checkpoint.

## External-input map

1. `/agent/query` receives authenticated user text. Pydantic bounds length,
   normalizes whitespace, and rejects invisible control characters before the
   graph is called.
2. `services/agent/harness.py` blocks direct instruction override, cross-order
   access, country-policy substitution, and out-of-domain requests.
3. Qdrant documents, MCP results, and memory records pass through
   `isolate_external_context`; instruction-like lines are removed and remaining
   content is labeled `UNTRUSTED_EVIDENCE`.
4. `data/pipelines/rag.py` sends immutable system policy separately from the
   delimited user request and untrusted evidence.
5. MCP tools accept typed inputs, are read-only, have four-second deadlines,
   and return typed outputs. The agent has no arbitrary SQL/code executor.
6. Generated text passes `validate_output` before delivery. It blocks internal
   instructions, exact warehouse data, addresses, and commercial terms.

## Implemented controls

- Secrets are environment-only (`.env.example` contains placeholders); real
  `.env` files are ignored. The API refuses a missing/short JWT secret.
- The model route is JWT-protected and limited per authenticated principal.
  `AGENT_RATE_LIMIT_REQUESTS` and `AGENT_RATE_LIMIT_WINDOW_SECONDS` control the
  application guard; HTTP 429 includes `Retry-After`.
- Ticket/order lookup is deny-by-default and checks an explicit per-user
  allowlist. Trace reads return 404 for non-owners.
- Agent traces record route, tool, guardrail, and output decisions without raw
  user text or secrets. Operational controls derive actor identity from JWT.
- RFP owner approvals and pause/resume/cancel are separate, audited mechanisms.
  Cancellation is terminal; resumption reuses the exact checkpoint.
- Direct and indirect prompt-injection tests are reproducible in
  `services/api/tests/test_agent.py`.

## NIST functions and prioritized roadmap

### Govern

Current: the inventory above assigns a business owner and separates TrackFlow
from provider responsibility. GDPR and CCPA/CPRA govern the data lifecycle.

- **P0 implemented:** human authorization remains outside model authority for
  irreversible/high-economic-impact actions.
- **P1 next:** approve a quarterly AI risk review and vendor/data-processing
  register owned by the CTO and privacy lead.

### Identify

Current: all model, RAG, memory, MCP, workflow, and telemetry boundaries are
listed with sensitive data and threat paths.

- **P0 implemented:** direct and indirect injection and cross-order access are
  explicit test cases.
- **P1 next:** maintain a data-flow diagram and automated dependency/SBOM scan
  for every release.

### Protect

Current: JWT authentication, deny-by-default resource authorization, typed
read-only tools, prompt separation, evidence isolation, output validation,
environment secrets, model-call rate limiting, and human checkpoints.

- **P0 implemented:** authenticated per-principal model rate limit and prompt
  injection neutralization.
- **P1 next:** move production secrets from environment injection to a managed
  vault with rotation and workload identity.

### Detect

Current: guardrail decisions, tools, routes, failures, model actions, and
operator controls are traced; the observability dashboard supports live status.

- **P0 implemented:** security/content/structural guardrail summaries and
  immutable action/event records.
- **P1 next:** alert on repeated injection, authorization denial, unusual model
  cost, and cross-tenant access patterns without logging message bodies.

### Respond

Current: terminal agent cancellation, explicit control actor/timestamp, safe
503 responses, and provider-independent logs support containment and analysis.

- **P0:** on suspected personal-data exposure, stop affected flows, preserve
  trace IDs, rotate affected credentials, notify Andrés/privacy lead, assess
  GDPR risk immediately, and notify AEPD within 72 hours when required.
- **P1:** add a CCPA/CPRA consumer-notification decision tree and twice-yearly
  incident tabletop.

### Recover

Current: checkpoints permit exact safe resume; cancellations cannot restart;
configuration and schema are versioned and reproducible.

- **P0:** restore only from a known-good revision, rotate credentials, validate
  authorization/injection tests, then resume from the stored checkpoint.
- **P1:** test encrypted backups, recovery objectives, deletion propagation,
  and post-incident customer/regulator communications quarterly.

## Open risks and treatment

| Gap | Risk | Treatment |
| --- | --- | --- |
| Process-local limiter | Multiple API replicas have independent counters | P1: enforce a second distributed principal/IP quota at gateway/Redis |
| Environment-injected production secrets | Host compromise can expose process environment | P1: managed vault, short-lived credentials, rotation evidence |
| Provider retention terms not represented in code | External model telemetry may exceed policy | P1: legal/vendor review, zero-retention setting, DPA evidence |
| No automated regulator deadline workflow | Human delay after a breach | P1: incident timer/escalation keyed to 72-hour GDPR deadline |

## Reproducible evidence

```bash
services/api/.venv/bin/python -m pytest \
  services/api/tests/test_agent.py \
  -k 'prompt_injection or rate_limit or normalized' -q
```

Expected: direct override is blocked before model execution, embedded external
instructions are removed while factual text remains, normalized input reaches
the model boundary, and the third request under a two-request test quota returns
HTTP 429.
