# TrackFlow Backend — Architecture Proposal

- **Author:** Armon Nasiri
- **Status:** Draft for CTO review, before the next sprint
- **Scope:** the first backend to live under `./services/`, plus the
  shape it should take as more services land
- **Company context:** [`CONTEXT.md`](../CONTEXT.md) is the source of
  truth; the reasoning below refers back to it constantly

> _This document proposes reasoning, not code. Whether FastAPI is
> installed or the project runs is out of scope; the goal is a
> shared architecture picture the team can build against._

---

## 1. What TrackFlow actually is (as it shapes architecture)

Facts that come straight from [`CONTEXT.md`](../CONTEXT.md) and
directly constrain the architecture:

1. **Multi-tenant SaaS.** Every request is scoped to a tenant.
   Cross-tenant data must never leak.
2. **Three very different user classes** with different latency /
   ergonomics needs:
   - Warehouse operators on handheld scanners (bursty writes,
     high tolerance for offline-then-sync).
   - Dispatchers on desktop (real-time reads, dashboards).
   - Account managers on desktop (long-form flows, quoting on
     live customer calls).
3. **Distinct bounded contexts** — Shipments, Routes, Warehouses,
   Drivers, Tenants, Incidents, Pricing (freight-quote). Each has
   its own lifecycle, invariants, and consumers.
4. **A canonical business-logic package already exists** —
   `@trackflow/business-logic` (Milestone 2). Rule `MONO-1` locks
   its formula (freight quote, service-tier eligibility, currency)
   as the one authoritative implementation. **The backend must
   consume it, never reimplement it.**
5. **Two countries, US and ES**, two currencies (USD / EUR),
   distinct timezones. Everything user-visible has to render in
   the tenant's country and timezone; everything internal is UTC.
6. **Volume shape:** hundreds to low thousands of shipments per
   tenant per day today, with a small number of large tenants.
   Not internet-scale. Not millions of concurrent users.

Together these facts favour **a modular monolith organised by
bounded context, deployed as one FastAPI service**, with a clean
seam toward future extraction. See §2 for why we're not choosing
the alternatives.

---

## 2. Chosen pattern — Modular Monolith (Package by Feature) with a thin Layered spine

The pattern has two axes:

- **Coarse split (top-level):** package-by-feature. One directory
  per bounded context (`shipments/`, `routes/`, `warehouses/`,
  `drivers/`, `tenants/`, `incidents/`, `pricing/`).
- **Fine split (inside each feature):** thin layered separation —
  `router`, `service`, `repository`, `schemas`, `models` — because
  a FastAPI handler that does everything inline becomes untestable
  the moment a real database and background jobs land.

This is the pattern the FastAPI community converges on for
production apps that outgrow the tutorial (see §5).

### 2.1 Why not raw MVC?

MVC is fine for a single-domain CRUD app, but TrackFlow has ≥ six
distinct domains today. In an MVC layout every model would sit
under `models/`, every route under `routes/`, and reading a single
feature would mean jumping between five folders. That drift got
punished on the reference project we spent 4 milestones on — the
sample dashboard's backend collapsed everything into one 392-line
`routes.py` and every change touched the same file. Package-by-
feature is what stops that.

### 2.2 Why not microservices?

- **Team size doesn't justify it.** Microservices need per-service
  CI, deploy, on-call, observability, and cross-service contract
  tests. We are one team.
- **The bounded contexts share a database today.** A shipment's
  route lookup, a driver's tenant lookup, a warehouse's country
  lookup — these are joins, not RPCs. Cutting a network boundary
  where a foreign key belongs is the classic distributed-monolith
  trap.
- **Extraction is cheap if the modular monolith is honest.** If
  `incidents/` grows into a service later, we lift the folder and
  its router; the internal contract is already the same shape as
  an HTTP contract because inside each feature we already talk
  through a `service.py` seam (not by reaching into another
  feature's models).

### 2.3 Why not serverless (Lambda-style)?

Warehouse handheld scanners talk in bursts of writes; account
managers hold quoting sessions open. Both benefit from a warm
process and a live DB connection pool. Cold-start latency and
per-invocation billing hurt more than they help at our current
scale. Revisit only if a specific subsystem (e.g. incident
webhooks) turns into a genuine spiky event source.

### 2.4 Consequence

The team makes decisions **inside** a feature freely and pays a
review-tax when a change crosses features (services calling other
services, or a new cross-cutting middleware). That's the trade
we want: local speed, global discipline.

---

## 3. Proposed folder and module structure

New backend service under `./services/api/` (name matches
convention set by the existing README hint —
`services/admin-api` in `services/README.md`; we'll use `api`
since it's the first and only backend surface today).

```
services/api/
├── pyproject.toml               # or requirements.txt — dependency manifest
├── README.md                    # how to run, env vars, endpoints index
├── .env.example                 # every var the service reads
├── src/
│   └── trackflow_api/
│       ├── main.py              # FastAPI app factory + include_router calls
│       ├── config.py            # Pydantic Settings — all env in one place
│       ├── db.py                # engine, session factory, dependency
│       ├── security.py          # auth deps (JWT / API key), tenant resolver
│       ├── logging.py           # structured logger setup (JSON to stdout)
│       ├── errors.py            # exception → HTTPException translator
│       ├── deps.py              # shared FastAPI Depends() (db, current tenant)
│       │
│       ├── shipments/           # ── bounded context: Shipment
│       │   ├── __init__.py
│       │   ├── router.py        #   /shipments/... routes only
│       │   ├── service.py       #   business flow, orchestrates repos + logic
│       │   ├── repository.py    #   DB access (SQLAlchemy queries)
│       │   ├── models.py        #   SQLAlchemy ORM models
│       │   └── schemas.py       #   Pydantic request / response DTOs
│       │
│       ├── routes/              # ── bounded context: Route (a Driver's daily plan)
│       │   └── ...
│       ├── drivers/
│       ├── warehouses/
│       ├── tenants/
│       ├── incidents/
│       ├── pricing/             # ── thin wrapper around @trackflow/business-logic
│       │   ├── router.py        #   POST /pricing/quote — reads request, calls…
│       │   ├── service.py       #   …bridge into the Node/TS business-logic pkg
│       │   └── schemas.py       #   Pydantic mirror of QuoteInput / QuoteResult
│       │
│       └── shared/              # ── genuinely cross-cutting utilities only
│           ├── pagination.py
│           ├── datetime_utils.py
│           └── money.py         # thin helpers; formulas stay in business-logic
└── tests/
    ├── conftest.py
    ├── shipments/
    │   ├── test_router.py       # HTTP-level tests via TestClient
    │   └── test_service.py      # pure-Python tests for the service layer
    └── ...
```

### 3.1 Separation criteria (why files land where they do)

- **A file that names an HTTP concept** (path, status code, request
  body shape) belongs in `router.py` or `schemas.py`.
- **A file that names a business concept** (rules, invariants,
  workflows across resources) belongs in `service.py`.
- **A file that names a persistence concept** (SQL, indices,
  ORM classes) belongs in `repository.py` / `models.py`.
- **Shared code moves to `shared/` only when it is used by ≥ 2
  features and does not encode domain knowledge.** Domain
  knowledge stays in the feature that owns it (rule `MONO-1`'s
  spirit applied inside a service).

### 3.2 What NOT to add to `shared/`

`shared/` is not a junk drawer. Anti-examples:

- A `format_currency` helper — currency formatting depends on the
  tenant's country; that belongs in the `pricing/` or `tenants/`
  feature, not in a shared file that grows into a
  business-rule dumping ground.
- A `Shipment` type — that's `shipments/schemas.py`.

### 3.3 Where the freight-quote formula lives

**Not here.** The `pricing/` feature is a *bridge* — it accepts an
HTTP request, validates it with Pydantic, and delegates to the
already-existing `@trackflow/business-logic` package (Milestone 2)
via a subprocess boundary or a small Python port kept 1:1 with
that module. Rule `MONO-1` forbids a parallel Python implementation.

Two viable options for the bridge, both compatible with this
architecture:

| Option                            | Pros                                     | Cons                                              |
| --------------------------------- | ---------------------------------------- | ------------------------------------------------- |
| **A. Call Node via subprocess**   | Zero drift — one implementation.         | Cold-start + serialization overhead per call.     |
| **B. Regenerate a Python mirror** | Fastest at request time.                 | Two implementations — must be kept in sync via `freight-quote-invariants` skill. |

Recommendation: start with **A** (call Node) for correctness. If
p95 latency at the pricing endpoint exceeds ~150ms in load
testing, revisit with a Python mirror plus a mandatory sync-check
CI job that runs `.agents/skills/freight-quote-invariants/scripts/verify.mjs`
against both.

---

## 4. FastAPI endpoint / router organisation

### 4.1 Grouping

- **One `APIRouter` per bounded context**, defined in that feature's
  `router.py`. Included by `main.py` with a URL prefix and a tag:

  ```python
  # sketch, not code to run
  app.include_router(shipments.router, prefix="/api/v1/shipments", tags=["Shipments"])
  app.include_router(routes.router,    prefix="/api/v1/routes",    tags=["Routes"])
  app.include_router(pricing.router,   prefix="/api/v1/pricing",   tags=["Pricing"])
  # ... one line per feature
  ```

- **URL version prefix is `/api/v1`.** A version segment is cheap
  now and buys us a clean off-ramp when the mobile driver app
  needs a breaking change we can't backport.

### 4.2 Route inventory (illustrative — actual endpoints follow the
same grouping)

| Prefix                       | Endpoint                              | Purpose                                                  |
| ---------------------------- | ------------------------------------- | -------------------------------------------------------- |
| `/api/v1/health`             | `GET /`                               | Liveness — kubernetes / uptime checks.                   |
| `/api/v1/shipments`          | `POST /`                              | Create a shipment (multi-tenant scoped).                 |
| `/api/v1/shipments`          | `GET /`                               | List shipments (paginated, filterable).                  |
| `/api/v1/shipments`          | `GET /{shipment_id}`                  | Detail.                                                  |
| `/api/v1/shipments`          | `PATCH /{shipment_id}/status`         | Warehouse operator progress updates.                     |
| `/api/v1/routes`             | `POST /`, `GET /`, `POST /{id}/assign` | Dispatch flows.                                          |
| `/api/v1/drivers`            | `GET /`, `POST /`, `PATCH /{id}`      | Driver management.                                       |
| `/api/v1/warehouses`         | `GET /`, `POST /`                     | Warehouse configuration by tenant.                       |
| `/api/v1/tenants`            | `POST /`, `GET /me`                   | Tenant onboarding, current tenant profile.               |
| `/api/v1/incidents`          | `POST /`, `GET /`, `PATCH /{id}`      | Incident capture and resolution.                         |
| `/api/v1/pricing`            | `POST /quote`                         | Freight quote — delegates to `@trackflow/business-logic`.|

### 4.3 Grouping rule for new endpoints

If a new endpoint is about **one** noun in the vocabulary above,
it goes into that feature's `router.py`. If it genuinely spans
two, it belongs in a new feature (e.g. an `incidents-on-a-route`
correlation report is a new `reporting/` feature, not a route
crammed into `routes/`).

---

## 5. What the FastAPI community actually does (research, cited)

Reading these before writing the proposal shaped the decisions
above. All three are the current consensus references for
production FastAPI layout:

1. **Official FastAPI — "Bigger Applications" guide.** Establishes
   the `APIRouter` per feature pattern and the app-factory
   convention. This is where the "one router per bounded context,
   `include_router` in `main.py`" idea comes from.
2. **`zhanymkanov/fastapi-best-practices`** (community-maintained
   reference on GitHub, ~11k stars at time of writing). This is
   where the *inside-a-feature* split — `router.py`, `schemas.py`,
   `service.py`, `models.py`, `repository.py`, `dependencies.py`
   — has become the de-facto template. The layout in §3 mirrors
   it deliberately so a new hire recognises the shape immediately.
3. **`tiangolo/full-stack-fastapi-template`** (from FastAPI's
   author). Contributes: the `src/<pkg>/` src-layout, Pydantic
   `Settings` in `config.py`, JWT security in a single module,
   Alembic migrations at the service root.

Where our proposal deviates from these references, it says so:

- We keep `/api/v1` versioning from day one (the FastAPI template
  omits it); rationale in §4.1.
- We deliberately keep the `pricing/` feature thin because our
  authoritative business logic is a JavaScript package in
  `packages/` (rule `MONO-1`), not native Python.

---

## 6. How frontend and backend coexist as separate systems

Already true in the monorepo today: `./uis/website` and
`./uis/backoffice` (Milestone 4) are Next.js apps, and this
proposal puts the API under `./services/api`. Same repo, separate
runtimes.

### 6.1 Communication contract

- **Transport:** HTTPS, JSON, `/api/v1/...` prefix.
- **Auth:** short-lived JWT in `Authorization: Bearer` header,
  refresh flow via HTTP-only cookie. `security.py` owns the
  Depends that resolves `current_user` and `current_tenant`; no
  handler ever touches raw tokens.
- **Tenant scoping:** the tenant id is derived from the JWT
  claim, **not** from a query parameter or a body field. This is
  what enforces the "no cross-tenant leaks" invariant in
  `CONTEXT.md`. A repository query that doesn't filter by
  `tenant_id` fails a lint rule (rule to be added: `SVC-1`).

### 6.2 CORS

- **Dev:** allow `http://localhost:3000` (`uis/website`) and
  `http://localhost:3100` (`uis/backoffice`) explicitly. Not
  `"*"` (learned that lesson on the reference dashboard —
  wildcard origin + `allow_credentials=True` is rejected by
  browsers and misrepresents the policy anyway).
- **Prod:** allow the two configured public origins from
  `settings.WEBSITE_ORIGIN` and `settings.BACKOFFICE_ORIGIN`,
  both read from env, both required (fail-fast on boot if unset).

### 6.3 Environment variables and secrets

- Every backend env var declared in `src/trackflow_api/config.py`
  via Pydantic `Settings`. Nothing else reads `os.environ`
  directly.
- `services/api/.env.example` mirrors that class one-to-one; CI
  fails if the two drift.
- Frontends use `NEXT_PUBLIC_API_BASE_URL` pointing at
  `http://localhost:8000/api/v1` in dev and the deployed origin
  in prod. Set per app via each app's `.env.local` (never
  committed).

### 6.4 Deploy shape

Two independent artifacts, same repo:

- Backend container: `services/api/Dockerfile` → one image.
- Frontends: each `uis/*` gets its own Vercel-style deploy.

Coupling stays at the API contract. A backend deploy does not
require a frontend redeploy (except when the OpenAPI schema
changes shape — that goes through the versioning gate in §4.1).

### 6.5 Repo layout stays a monorepo (no split)

We already have shared packages (`packages/business-logic`)
consumed by frontends today. A repo split would need a private
registry plus release cadence for those packages. Not worth it
until we hit a team-size boundary the monorepo can't hold.

---

## 7. Risks and points of attention

At least two, per the brief — five here because they're the ones
most likely to cause real pain if the team doesn't follow the
structure above.

### R1 — The `shared/` folder becomes a business-logic dumping ground

**What goes wrong:** it's the easiest place to drop code, so people
do. Six months in, `shared/utils.py` is 800 lines, half the
project imports it, and a change to a "shared helper" silently
alters four features.
**Guardrail:** every file added to `shared/` requires a PR
description sentence saying which ≥ 2 features consume it and
naming why the code isn't domain-owned. If neither is true, the
file belongs inside a feature.

### R2 — Business logic drifts from `@trackflow/business-logic`

**What goes wrong:** a developer, tired of the Node subprocess
call in `pricing/service.py`, quietly ports the freight-quote
formula to Python "just for this endpoint". Two implementations,
one wrong; sales quotes and invoices disagree.
**Guardrail:** rule `MONO-1` already forbids it, and
`.agents/skills/freight-quote-invariants/` gives a runnable
check. Add a CI job that runs
`npm run verify:freight-quote` on every PR that touches
`services/api/src/trackflow_api/pricing/`.

### R3 — Tenant scoping enforced in handlers instead of repositories

**What goes wrong:** the first version of `shipments/service.py`
does `db.query(Shipment).all()` and filters by `tenant_id` in
Python. The next handler forgets the filter and returns every
tenant's shipments in one JSON response.
**Guardrail:** all queries live in `repository.py`, and the
repository takes a `tenant_id` as a required argument — no
overload without it. This is a testable invariant; a lint rule
(`SVC-1`) can enforce that no `db.query(...).all()` /
`select(Model)` appears outside `repository.py`.

### R4 — Cross-feature imports (`shipments/` → `routes/models.py`)

**What goes wrong:** the moment `shipments/service.py` does
`from trackflow_api.routes.models import Route`, we've created
a coupling that will fight future extraction and make circular
imports likely.
**Guardrail:** features may import from `shared/`, from their own
`schemas.py` / `service.py`, and — grudgingly — from another
feature's public **schemas**, never its `models.py`. Cross-feature
behaviour goes through the other feature's `service.py`
function (the same seam we'd hit if it were a separate service).

### R5 — Timezone / currency handled ad-hoc in the API layer

**What goes wrong:** a handler formats currency directly in a
response by hard-coding `"$"`. A Spanish tenant sees a dollar
sign. A dispatcher in Los Angeles sees a UTC timestamp on their
shift roster.
**Guardrail:** currency formatting only happens in the UI layer
(the API returns raw numbers + currency code); timestamps are
always ISO-8601 UTC in the API; the tenant's country and
timezone live on the JWT and are applied in the UI. Two
`shared/` files (`money.py`, `datetime_utils.py`) exist only to
enforce this at the boundary and are the *only* helpers allowed
to touch either concern.

---

## 8. Summary — one paragraph for the CTO

TrackFlow is a mid-market, multi-tenant SaaS with a handful of
distinct bounded contexts, and its authoritative business logic
already lives in `@trackflow/business-logic`. The right backend
shape for that is a **modular monolith organised by feature**,
built on **FastAPI**, with an internal seam per feature
(`router`/`service`/`repository`/`schemas`/`models`) that mirrors
the community reference layouts (`zhanymkanov/fastapi-best-practices`,
FastAPI's own "Bigger Applications" guide, and
`tiangolo/full-stack-fastapi-template`). URLs are versioned
under `/api/v1`; frontends and backend coexist in the monorepo
but ship as independent artefacts with explicit CORS origins and
env-var-declared secrets. The main risks are all discipline risks —
`shared/` bloat, business-logic drift, tenant-scope leaks,
cross-feature import creep, and ad-hoc formatting — and each has
a named guardrail above.
