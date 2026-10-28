# TrackFlow OWASP Top 10 audit and remediation

Audit date: 2026-10-28  
Scope: CX support agent, carrier selector, returns approval, return-policy RAG,
tracking/inventory API, backoffice/operations dashboard (SSE and WebSocket),
company-tools MCP, RFP workflow, and B2B-facing UI paths.

## Executive result

Four baseline findings required immediate remediation. All are fixed in this
delivery: cross-order agent authorization, public exposure of internal service
ports, root container execution, and a high-severity vulnerable DNS parser.
No unresolved critical finding remains. One low-severity `deepmerge` advisory
remains in the development-only Jest toolchain because no patched upstream
version is available; it is neither shipped nor used to merge runtime input.

## Baseline findings and fixes

| ID | OWASP | Severity | Baseline | Remediation and proof |
| --- | --- | --- | --- | --- |
| TF-01 | A01 | Critical | A support question could name another order unless ownership was checked before the incident tool | `authorize_ticket` denies by default and only admins/explicit user allowlists pass (`services/api/routers/agent.py:29`); cross-user tests prove denial |
| TF-02 | A05 | Critical | Compose published MCP, Flower, Redis, and Qdrant on every host interface | Every published development port is now loopback-only (`docker-compose.yml:16-157`); host UFW permits only 22/80/443 |
| TF-03 | A05 | High | Backend and MCP images had no explicit runtime user | Both images declare `USER trackflow` (`services/Dockerfile:36`, `mcps/company_tools/Dockerfile:20`) and verification prints their nonzero UIDs |
| TF-04 | A06 | High | GitHub alert #38: `dnspython` 2.8.0 crafted-name CPU denial of service | Direct floor `dnspython>=2.9.0` (`services/api/pyproject.toml:24`) and locked 2.9.0 artifact (`services/api/uv.lock:1129`) |

## OWASP Top 10 evaluation — three independent lanes

### A01:2021 Broken Access Control — applies, remediated

- **Backend:** JWT dependencies load an active database user and self/admin
  checks reject another user's record (`services/api/security.py:176,213`).
- **Frontend:** route guards improve UX only; the audit does not treat them as
  authorization. Every protected fetch sends the token and the API rechecks it.
- **Agent:** incident/order tools are deny-by-default per principal
  (`services/api/routers/agent.py:29`). MCP tools are read-only and scoped;
  trace access returns 404 for a non-owner. TF-01 is covered by automated tests.

### A02:2021 Cryptographic Failures — applies, controlled

- **Backend:** JWT refuses missing or under-32-byte keys
  (`services/api/security.py:49`); passwords use bcrypt; real credentials are
  ignored environment data. Production TLS terminates at the reverse proxy.
- **Frontend:** HTTPS is mandatory in production. Tokens remain in localStorage
  because the course auth contract requires it; this raises XSS impact and is a
  documented medium residual risk. Short expiry and centralized 401 clearing
  reduce persistence; HttpOnly/SameSite cookie migration is P1.
- **Agent:** carrier, model, webhook, and MCP credentials never enter prompts,
  telemetry, or tracked files. Provider transport must be HTTPS.

### A03:2021 Injection — applies, remediated

- **Backend:** Pydantic/SQLModel typed parameters and ORM expressions are used;
  no request text is concatenated into SQL or shell commands.
- **Frontend:** React rendering escapes values; the audit found no
  `dangerouslySetInnerHTML`, `eval`, `innerHTML`, or `new Function` use.
- **Agent:** direct prompt overrides are blocked and external evidence is
  instruction-stripped/marked untrusted (`services/agent/harness.py:37,188`).
  There is no arbitrary code/SQL tool. Output leakage validation runs at line
  212. Direct and indirect injection tests are reproducible.

### A04:2021 Insecure Design — applies, controlled

- **Backend:** stock is derived from immutable movements; outbound writes reject
  negative stock before persistence. Model calls have a per-principal quota
  (`services/api/rate_limit.py:29`).
- **Frontend:** outbound UI warns before the API's authoritative check and shows
  readable errors; it cannot directly mutate stock.
- **Agent:** carrier selection is a recommendation; tools are read-only. RFP and
  high-impact approval paths stop for a named human
  (`data/pipelines/rfp_intake/approval.py:158,195`). Pause and approval remain
  separate, preventing an operational control from impersonating consent.

### A05:2021 Security Misconfiguration — applies, remediated

- **Backend:** explicit CORS rejects wildcard origins
  (`services/api/main.py:99`); unhandled errors return fixed JSON without
  internals (`services/api/main.py:118`). Runtime containers are non-root.
- **Frontend:** clickjacking, MIME-sniffing, referrer, camera, microphone, and
  geolocation headers are centrally configured
  (`uis/backoffice/next.config.ts:18`, `uis/website/next.config.ts:9`).
- **Agent:** no carrier-change, dispatch, arbitrary HTTP, or write-capable MCP
  permission is exposed. Internal services bind only to loopback/private Compose
  networking. TF-02 and TF-03 are fixed.

### A06:2021 Vulnerable and Outdated Components — applies, remediated/monitored

- **Backend:** TF-04 upgrades the high-severity `dnspython` alert to 2.9.0.
  Images pin major/minor families and the lockfile records exact artifacts.
- **Frontend:** `npm audit` reports six paths to one low `deepmerge` advisory in
  Jest/ts-jest. No fixed upstream release exists, and Jest is development-only;
  `npm audit --omit=dev` reports zero production vulnerabilities. Recheck the
  development advisory on every dependency update.
- **Agent:** LangGraph, OpenAI client, Qdrant client, and MCP packages are locked;
  Dependabot remains the release gate. No unresolved high/critical alert remains
  once this PR reaches the default branch.

### A07:2021 Identification and Authentication Failures — applies, controlled

- **Backend:** expired, malformed, wrongly signed, deleted-user, and inactive-user
  JWTs fail; bcrypt inputs over 72 bytes are rejected; login errors do not reveal
  password material.
- **Frontend:** every protected request uses one auth wrapper; 401 clears the
  session and returns to login. Client-decoded roles are display hints only.
- **Agent:** chat, traces, guardrail summaries, SSE, and WebSocket controls all
  require authentication. WebSocket actor identity is derived server-side from
  the JWT and cannot be supplied by a client command.

### A08:2021 Software and Data Integrity Failures — applies, controlled

- **Backend:** npm and Python lockfiles include integrity hashes; CI runs complete
  tests/builds before merge. No runtime package installation uses an untrusted
  request value.
- **Frontend:** `npm ci` consumes the committed lock. External content is rendered
  as data, not executable HTML.
- **Agent:** model output is never trusted as authorization. Typed output guards,
  deterministic arbiters, and human checkpoints validate it before consequential
  transitions. RFP resume uses the stored checkpoint rather than client state.

### A09:2021 Security Logging and Monitoring Failures — applies, controlled

- **Backend:** fixed client errors exclude stack traces while server logs retain
  correlation context. Telemetry pseudonymizes users and allowlists properties.
- **Frontend:** errors, performance, navigation, and API outcomes flow through the
  telemetry service without email/password/message bodies.
- **Agent:** route, tool, guardrail, approval, and control decisions are durable;
  operational commands include server-derived actor and timestamp. SSE/WebSocket
  dashboards expose intervention state without secrets.

### A10:2021 Server-Side Request Forgery — applies, controlled

- **Backend:** no public endpoint accepts a URL for the server to fetch. API and
  telemetry service destinations come from deployment configuration.
- **Frontend:** Next rewrites use administrator-provided fixed origins, never a
  query/body URL. External talent origin is a fixed configuration value.
- **Agent:** MCP and model base URLs are environment-controlled; users can select
  only named typed tools and cannot request arbitrary HTTP. Tool timeouts bound
  resource use. P1 is outbound egress allowlisting at the host/cloud layer.

## Server and network hardening

The target host policy is versioned in `deploy/hardening/` and documented in
`docs/security/server-hardening.md`:

- dedicated `trackflow` deploy/operations user;
- root, password, keyboard-interactive, X11, and forwarding SSH disabled;
- code/log directories `trackflow:trackflow 0750`; configuration
  `root:trackflow 0750` (secret files `0640`);
- UFW default-deny inbound with only 22, 80, and 443 public;
- application/data services loopback/private-network only;
- backend and MCP containers execute as non-root.

Host application intentionally requires `--apply` plus an approved public-key
file so auditing the script cannot lock out a server. The operator must retain
console access and verify a second key-only session before logout.

## Reproducible verification

```bash
# Dependency remediation
rg -n 'dnspython>=2.9.0|version = "2.9.0"' \
  services/api/pyproject.toml services/api/uv.lock

# Application security
services/api/.venv/bin/python -m pytest \
  services/api/tests/test_agent.py \
  services/api/tests/test_auth.py \
  services/api/tests/test_error_handling.py -q

# Port/interface and container policy
docker compose config
docker compose build backend company-tools-mcp
docker compose run --rm --no-deps backend id
docker compose run --rm --no-deps company-tools-mcp id

# Target Linux host (after controlled deployment)
deploy/hardening/verify-host.sh
```

Expected container identity: a nonzero UID named `trackflow`. Expected host
listeners: public 22/80/443 only; all TrackFlow service ports are loopback or
private-network listeners.

## Residual risks and sign-off

| Risk | Severity | Decision |
| --- | --- | --- |
| LocalStorage bearer token increases impact of a future XSS | Medium | Accept for current course contract; migrate to secure HttpOnly SameSite cookie and nonce-based CSP before public production |
| Jest-only `deepmerge` prototype-poisoning advisory has no patch | Low | Isolated to development; never merge user data through it; monitor upstream |
| Application rate limiter is process-local | Medium | Add gateway/Redis distributed quota for multi-replica production |
| Host hardening proof depends on the actual VPS | Operational | Run the guarded scripts through console access and attach `hardening-proof.txt` at deployment sign-off |

Code-level sign-off: all critical/high findings identified by this audit are
remediated with source and automated evidence. Production sign-off additionally
requires the target-host verification output and TLS certificate check.
