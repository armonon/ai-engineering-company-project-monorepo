# Progress — TrackFlow monorepo

Rolling log of substantive changes. Newest first.

---

## 2026-08-29 · Public TrackFlow demonstration

**Branch:** `codex/sync-live-trackflow-site`

- Published the TrackFlow public landing page at
  `https://trackflow-coursework-demo.armonon.chatgpt.site` while keeping the
  authenticated backoffice and FastAPI service in the Docker demonstration.
- Updated the canonical website metadata, mobile navigation, public copy, and
  branded Open Graph/X preview asset to match the hosted version.
- Added the live URL to the repository README so the deployment is directly
  traceable from GitHub.

Verification on this branch:

- Root typecheck, all production builds, and the website lint pass.
- 79 JavaScript/TypeScript tests and 322 FastAPI tests pass.
- `npm audit` reports zero known vulnerabilities.
- The public deployment returns HTTP 200, and the production website build
  emits the canonical Open Graph and X image URLs.

## 2026-08-29 · Docker runtime dependency correction

**Branch:** `codex/docker-runtime-dependency`

- Promoted `httpx` from the API's development dependency group to its runtime
  dependencies. `email_service.py` imports it during application startup, so
  the backend container could not boot when production dependencies were
  installed without the development group.
- Discovered through the first live Docker Desktop Compose run on Apple
  Silicon: both images built, but the backend health check failed with
  `ModuleNotFoundError: No module named 'httpx'` and correctly prevented the UI
  from starting.
- Rebuilt the backend image from the corrected lockfile and re-ran the complete
  Compose stack before marking the containerization deliverable verified.
- Live browser requests then exposed missing Alpine-native Tailwind/Lightning
  CSS binaries in the UI image. Declared the Linux GNU and musl packages for
  both `amd64` and `arm64`, included root optional dependencies during the
  workspace install, stopped shadowing image dependencies with a stale named
  volume, and isolated container-side Next.js caches from host-native caches.
- Allowed the two loopback development hosts in every Next.js application so
  browser verification can load development chunks and hydrate normally when
  Compose is opened through either `localhost` or `127.0.0.1`.

Verification on this branch:

- Root typecheck and production builds pass for every workspace.
- 79 JavaScript/TypeScript tests and 322 FastAPI tests pass.
- Fresh Compose recreation returns HTTP 200 from the API (`:8000`), website
  (`:3000`), backoffice (`:3001`), and same-origin API proxy
  (`:3001/trackflow-api`).
- Browser verification renders the public TrackFlow site and confirms the
  protected backoffice redirects an unauthenticated visitor to `/login`.

## 2026-08-28 · Runtime readiness corrections

**Branch:** `codex/runtime-readiness-corrections`

- Routed browser API calls through a same-origin Next.js rewrite that reaches
  the FastAPI container as `backend`, satisfying the Compose service-name
  contract without exposing Docker DNS names to the host browser.
- Added the published backoffice port to explicit CORS defaults and made the
  production origin list configurable without permitting wildcards.
- Replaced the unused vulnerable `python-ecdsa` dependency chain with PyJWT;
  TrackFlow signs and verifies only HS256 tokens and rejects signing keys
  shorter than 32 bytes.
- Added mobile backoffice navigation, longest-route active matching, truthful
  inventory POST response types, and request/navigation regression tests.
- Scoped dotenv loading to `services/api/.env`, preventing native API sessions
  from inheriting Docker-only paths from the Compose root `.env`.
- Migrated all three UI linters from the removed compatibility-adapter pattern
  to Next.js 16's native flat ESLint config and resolved the stricter effect
  scheduling findings.

Verification on this branch:

- Root typecheck and production builds pass for every workspace.
- 79 JavaScript/TypeScript tests and 322 FastAPI tests pass.
- All three UI linters pass and `npm audit` reports zero vulnerabilities.
- A native runtime smoke test returned the FastAPI health response through the
  backoffice `/trackflow-api` rewrite and rendered the guarded inventory route
  without browser console warnings.
- Docker Compose could not be executed on this Mac because no Docker runtime is
  installed; the Compose service-name contract is covered by the rewrite,
  environment, CORS, and runtime proxy checks above.

---

## 2026-08-28 · Repository hardening and submission cleanup

**Branch:** `codex/repository-hardening`

- Reconciled the shared MX/ES TrackFlow context with the inventory-specific
  LA/ZGZ assignment through an explicit, narrow precedence rule.
- Replaced the blanket `.openclaw/` ignore with a public-deliverable
  allowlist while keeping credentials, memory, and runtime state denied by
  default. The warehouse agent remains separate from the coursework steward.
- Explained the two historically valid Milestone 5 snapshots and kept the
  warehouse-agent milestone unnumbered until 4Geeks supplies its official
  project identifier.
- Made `npm run test` genuinely repository-wide: every npm workspace now has
  `typecheck`, `test`, and `build`; the root test also runs pytest through
  `uv` or the existing API virtual environment. Added real website and talent
  tracker unit tests and removed the nested workspace lockfile.
- Upgraded all three UIs together to Next.js 16.3.3, resolved the remaining
  `nanoid` advisory, made the root lockfile carry Lightning CSS's Linux native
  binary for portable `npm ci`, and added `httpx2` so the FastAPI test client
  runs without its former Starlette deprecation warning.
- Added GitHub Actions verification for pull requests and `main`. Updated the
  GitHub description/topics, disabled the stale template flag, enabled Issues,
  and enabled secret scanning with push protection.
- Updated English/Spanish orientation, testing instructions, current stack,
  and historical audit notes that had become misleading.

Verification on the hardening branch:

- `npm run typecheck` passes for every workspace.
- 69 JavaScript/TypeScript tests pass; the shared types package also compiles
  under its own strict TypeScript configuration.
- 318 FastAPI tests pass without warnings.
- All packages and all three Next.js 16.3.3 production applications build.
- `npm audit --omit=dev` reports zero vulnerabilities.

---

## 2026-08-28 · Milestone branch recovery and OpenClaw coursework agent

**Branch:** `codex/openclaw-coursework-agent`

- Restored the milestone branches that could be proven from original commit
  and pull-request history: Milestones 1, 2, 3, 4, 5, 6, and 9.
- Added `MILESTONES.md` as the canonical submission branch map. Milestones 7
  and 8 remain explicitly unmapped instead of being inferred from feature
  branch names.
- Added current OpenClaw workspace files (`IDENTITY.md`, `SOUL.md`,
  `TOOLS.md`) and a setup runbook in `OPENCLAW.md`.
- Added a read-only milestone snapshot audit skill and read-only 4Geeks API
  status skills. Secrets stay in the ignored root `.env` file.
- Corrected the root README and tech context, which still described the
  populated repository as an unused starter template.

Verification completed on the organization branch:

- OpenClaw sees all five coursework skills; gateway configuration and local
  gateway authentication pass their health checks.
- `npm run typecheck`, `npm run test`, and `npm run build` pass after the
  documented `npm run bootstrap` fresh-clone step.
- The FastAPI pytest suite passes in an ignored local virtual environment.
- The read-only milestone audit verifies every published snapshot against its
  exact historical commit and required deliverable paths.

Local OpenClaw model authentication and the private `TOKEN_4GEEKS` value are
still user-supplied credentials; neither is stored in Git.

The active development repository is
`armonon/ai-engineering-company-project-monorepo`; the separate
`4geeks-coursework` repository remains a historical archive.

---

## 2026-08-28 · Milestone 5 inventory with SQLModel and a second database

**Branch:** `milestone-5-inventory-orm`

`services/api` now holds two databases and uses each deliberately:
TinyDB keeps users, auth, profiles, suppliers and incidents; **Supabase
(PostgreSQL, via SQLModel)** holds SKUs and stock movements. Entity
names come from `docs/CONTEXT-inventory-trackflow.md`.

### What was added

- `models.py` — `SKU`, `StockEntry`, `StockExit` as SQLModel
  `table=True` classes. These are the only ORM models in the codebase.
- `schemas.py` — new file, Pydantic request/response schemas. Separate
  from the ORM by design; no endpoint returns a SQLModel object.
- `routers/inventory.py` — `APIRouter(prefix="/inventory")`, six
  endpoints.
- `database.py` — SQLModel engine plus a `get_db` dependency yielding
  one session per request. No global session.
- `seed_inventory.py` (`uv run seed-inventory`) — the CONTEXT seed data,
  idempotent.
- `tests/test_inventory.py` — 29 tests.

### Decisions worth remembering

- **`get_db` was already taken.** TinyDB's accessor had that name, and
  adding the SQLModel dependency silently shadowed it — every TinyDB
  table broke. The TinyDB one is now `get_tinydb()`; `get_db` is the
  SQLModel dependency the milestone requires.
- **No SQLModel `Relationship()`.** `models.py` uses
  `from __future__ import annotations`, so SQLAlchemy sees
  `list["StockEntry"]` as a class name and fails to map it. The foreign
  keys are declared and enforced at database level; `routers/inventory.py`
  loads related SKUs with one explicit batched query instead, which is
  N+1-free and easier to follow than relationship loading.
- **Stock is per SKU per warehouse** (CONTEXT rule 6). The response
  carries `current_stock` for the SKU's own warehouse plus a
  `stock_by_warehouse` breakdown, so the scoping is visible rather than
  implied.
- **The engine is lazy.** Building it at import would have required
  DATABASE_URL and a reachable Supabase before *any* route could serve,
  including auth. Startup logs a warning when it is unset and the API
  boots anyway — which is also why the suite runs without Postgres.
- **`user_uuid` is the TinyDB user id as a string**, the convention
  `models.py` and `security.py` already documented before this
  milestone. No user table exists in Supabase.

### Verification

- 315 backend tests (29 new). The inventory tests run on SQLite so the
  suite needs no credentials.
- The whole API was additionally driven against **real PostgreSQL 16**:
  tables created on startup, the exact CONTEXT rejection message,
  per-warehouse scoping, and no exit row persisted after a rejection.
- Mutation-checked: removing the stock guard fails 3 tests, aggregating
  stock globally fails the warehouse test, and reading the SKU per
  movement fails the N+1 test with 10 SELECTs instead of 4.
- `ruff` clean.

---

## 2026-08-14 · Fold Milestone 2 into `packages/programming-fundamentals`

**Branch:** `milestone-2-fold-in`

Prior work from the draft PR `milestone-2-programming-fundamentals`
(dated 2026-08-05) had been sitting open. Rather than closing and
discarding it, the salvageable pieces landed in their proper homes
under the Milestone 4 workspace layout:

- `packages/programming-fundamentals/` — new `@trackflow/programming-fundamentals`
  workspace with the M2 domain types (Product, Shipment, Carrier,
  InventoryMovement), collection filters, search helpers,
  transformations (shipping cost, carrier scoring, aggregations),
  and business-rule validations. 24 `node --test` tests pass.
- `docs/company-context/` — the M2 briefings
  (00-trackflow-company-briefing, 01-web-fundamentals,
  02-coding-fundamentals) kept as reference material.
- Root `package.json` bootstrap / test scripts extended to cover
  the new workspace.

**Dropped from the original PR:**
- `uis/website/*.html|*.js` — Milestone 4 already provides a
  Next.js website at `uis/website/`; keeping the old static
  version would overwrite it.
- `packages/shared/package.json` change — Milestone 4 conventions
  use `@trackflow/<workspace>` scoping; the template's stub
  `@repo/shared-types` stays grandfathered (MONO-3).
- Root-level `src/` — the code lives in a workspace now, not at
  the tree root.

Delivery workflow: `npm run bootstrap && npm run test && npm run demo:programming-fundamentals`
all exit 0.

---

## 2026-08-02 · Milestone 4 — AI-driven engineering infrastructure

**Branch:** `milestone-4`

### Delivered

- **CONTEXT.md** replaced with the TrackFlow scenario. Placeholder
  Spanish variant removed — the CONTEXT is one file, one language,
  because it is code-adjacent.
- **`memory-bank/`** seeded with `projectbrief.md`, `techContext.md`,
  and this `progress.md`. Every file is anchored to CONTEXT.md so
  the "business + technical" pair is not a template.
- **`AGENTS.md`** at repo root: names the memory-bank files the
  agent must read at the start of every session, spells out a 5-step
  pre-commit workflow, and lists the do-not-modify surfaces that
  require explicit developer confirmation.
- **`.agents/rules/`** — one file (`monorepo-conventions.md`) with
  three scoped, actionable rules (`MONO-1..3`). More will accrete as
  we discover them.
- **`.agents/skills/freight-quote-invariants/SKILL.md`** — a
  reusable, verifiable skill for confirming freight-quote logic
  hasn't drifted from CONTEXT.md, with an executable acceptance
  script (`scripts/verify.mjs`).
- **`packages/business-logic/`** — Milestone 2 stand-in:
  `quoteShipment(input)` implementing the freight-quote formula from
  CONTEXT.md. Ships with `node --test` unit tests.
- **`uis/website/`** — Next.js 15 corporate site, App Router,
  Tailwind v4, TypeScript strict. Sections: hero, offering,
  countries served, pricing tiers, contact. Per-page metadata.
- **`uis/backoffice/`** — Next.js 15 internal app, App Router.
  Home route (`/`) is the account-manager quote calculator. It
  imports `@trackflow/business-logic` — the module is not copied.

### Deferred

- CI workflow (`MONO-2`) — noted in `techContext.md` and in
  `.agents/rules/monorepo-conventions.md`.
- Shared UI kit — deferred until a third `uis/*` appears.
- Backend services under `services/` — Milestone 5+.
- Merging `@repo/shared-types` and `@trackflow/business-logic`.

### Delivery workflow — end-of-branch pass

Ran all five steps from `AGENTS.md § Delivery workflow` before the
final commit:

1. `git status` — clean tree after each phase commit.
2. `npm run typecheck` — three workspaces, exit 0.
3. `npm run test` — 5/5 tests pass in `@trackflow/business-logic`;
   backoffice / website have placeholder `test` scripts pending
   real coverage (rule MONO-2 stopgap, marked `TODO(MONO-2)` in
   their `package.json` for a follow-up).
4. `npm run build` — all three workspaces build cleanly with
   turbopack.
5. `npm run verify:freight-quote` — skill script prints
   `freight-quote-invariants: OK (10 assertions)`.

### Notes on rebuilds vs. migrations

The public website's Milestone 1 version and the Milestone 2
TypeScript module are not present in the fork at the start of this
milestone. Both were **built from CONTEXT.md** so this delivery is
self-contained and reflects TrackFlow rather than a generic company.
When earlier milestones land, `MONO-1` (single source of truth) is
the guardrail that keeps the imports pointed at
`packages/business-logic`.

---

## Error handling audit (`feature/error-handling-audit`)

Cross-cutting pass over the whole repository. No new features: the
deliverable is the same platform, failing better. Full report in
[`docs/ERROR_HANDLING_AUDIT.md`](../docs/ERROR_HANDLING_AUDIT.md).

### Behaviour that changed

- **`services/api/main.py` now has a global `Exception` handler.** Every
  error response from the API is JSON. It used to be possible to get the
  plain-text body `Internal Server Error`, which the frontend then failed
  to parse — surfacing to the user as `Unexpected token 'I'`.
  Reproducible trigger: a CSV field over 128 KB uploaded to
  `/api/incidents/analyze`.
- **Exception text no longer reaches clients.** The real exception is
  logged server-side; responses carry a fixed, human-readable `detail`.
  This closed a leak where a password sent as a non-string JSON value
  came back inside a Pydantic validation error.
- **New incidents reject containers.** `{"title": {"a": 1}}` used to be
  stored as the literal `"{'a': 1}"`.
- **`AuthProvider` distinguishes a rejected token from an unreachable
  server.** Previously any failure cleared the token, so an API blip
  logged people out permanently. A transport failure now keeps the
  session and renders a recoverable state with Retry.
- **Scripts exit non-zero with advice on `stderr`**, never a traceback.
  Unreadable input exits 2, a parse failure exits 1.
- **Both Next apps now have error boundaries** (`app/error.tsx`,
  `app/global-error.tsx`). There were none, so a render-time exception
  blanked the page to Next's "Application error: a client-side exception
  has occurred (see the browser console)". Note the contract differs by
  major: Next 15 passes `reset`, Next 16 passes `unstable_retry` — the
  backoffice and the tracker each use their own version's name.

### New shared module

`uis/*/lib/errors.ts` — `toUserMessage(error, fallback)` and
`readJson(res)`. Every user-facing error render goes through it. Server
messages written for humans pass through; browser and parser noise
(`Failed to fetch`, `Unexpected token`, stringified bodies) is replaced.
Duplicated into both `uis/backoffice` and `uis/talent-pipeline-tracker`
deliberately — they are separate Next apps with separate `@/` roots, and
promoting it to `packages/` is the follow-up if a third UI appears
(rule MONO-2).

### Verification

- 196 backend tests (19 new in `tests/test_error_handling.py`).
- Every backend fix mutation-checked: reverting it makes its test fail.
- 47 browser assertions against the running stack, including a
  deliberately killed API, asserting no technical text ever reaches the
  screen and every error state offers a way forward.

### Deferred

- The two `lib/errors.ts` copies (see above).
- `uis/website` needs nothing — it is static and has no async work.
- `packages/incident_analyzer` still raises precise exceptions rather
  than handling them; that is correct for a library, and the handling
  now lives at the route and script boundaries.

---

## AUTH-088 test suite (`feature/auth-test-suite`)

Unit tests for the authentication API, plus the two backlog tickets.
Plan, run instructions, and results in [`TESTING.md`](../TESTING.md).

### What was added

- `services/api/tests/conftest.py` — shared fixtures; each test gets its
  own TinyDB file.
- Six per-endpoint modules (`test_register`, `test_login`, `test_token`,
  `test_forgot_password`, `test_reset_password`, `test_change_password`),
  73 tests, three tiers each.
- `test_suppliers_business_rules.py` — 17 tests for API-042.
- **Jest**, which did not exist before: `uis/backoffice/jest.config.ts`
  plus `__tests__/` with 35 tests for the utility layer (FE-019).
- `pytest-cov` and `httpx` as dev dependencies.

### Behaviour that changed

Four bugs the tests found, all fixed here:

1. **`/auth/forgot-password` leaked account existence on a mail failure.**
   The route trusted the sender to swallow its own errors; the sender only
   catches `httpx.RequestError`. Anything else made a *registered* address
   return 500 while an unknown one returned 200 — an enumeration oracle
   that appears during a provider incident. The send is now guarded in the
   route, where the security property lives.
2. **`formatRate` rendered "NaN €"** for a supplier with a missing rate.
   Guard checks `Number.isFinite`, not truthiness — 0 is a real rate.
3. **`formatDate` rendered "Invalid Date"**, and its `try/catch` could
   never fire: `new Date("nonsense")` does not throw. The error-handling
   audit walked past this one.
4. **The supplier directory was readable without a token.** This was a
   deliberate AUTH-01 exemption, kept open "until the frontend starts
   sending tokens" — a condition that has since been met, so both reads
   are now protected. Checked in a browser afterwards: the directory page
   still loads, because the frontend was already sending the token.

### Notes

- The root `npm run test` script hardcoded two workspaces, so the new Jest
  suite never ran from the root. It now uses `--workspaces --if-present`,
  matching `typecheck` and `build`.
- Jest reports 46% on `lib/` because the uncovered lines are the `fetch`
  wrappers. Mocking `fetch` to raise that number would assert nothing
  about whether the API agrees; those paths are covered by Playwright
  against a running backend. `errors.ts` — the part Jest is right for —
  is at 97%.

---

## Tracker build fix (`fix/tracker-build`)

`uis/talent-pipeline-tracker` did not build. It had not built for several
milestones, and each PR since has carried the failure as a disclosed,
pre-existing problem. Fixed here.

### The actual cause

The monorepo was running **two majors of Next and two minors of React**:

| Workspace | Next | React |
|---|---|---|
| `uis/backoffice` | 15.5.22 | 19.1.0 |
| `uis/talent-pipeline-tracker` | 16.2.12 | 19.2.4 |

npm hoists one version to the repo root and nests the other inside the
workspace. `next@15` won the root, so the tracker got
`uis/talent-pipeline-tracker/node_modules/next` — while `next`'s own
dependencies stayed hoisted at the root.

Turbopack could not resolve those hoisted dependencies from a
workspace-nested package. The errors arrived one at a time —
`picocolors`, then `source-map-js`, then
`@swc/helpers/_/_interop_require_default` — which made it look like a
missing-dependency problem. It was not: every one of them was installed,
just one directory level further up than turbopack would look.

Backoffice has a nested `postcss` too and builds fine, because its copy
sits at `<root>/node_modules/next/node_modules/postcss`. Only the
*workspace*-nested case fails.

### The fix

One version of each framework package across the monorepo. The tracker
moves to `next@15.5.22` and `react@19.1.0`, matching the backoffice, so
nothing nests: **all three `uis/*` workspaces now have zero nested
packages.**

Three consequential edits came with it:

- `app/error.tsx` / `app/global-error.tsx` — the error boundary callback
  is `reset` on Next 15 and `unstable_retry` on Next 16. Reverted to
  `reset`.
- `eslint.config.mjs` — rewritten to the `FlatCompat` style the backoffice
  uses. The extensionless `eslint-config-next/core-web-vitals` imports are
  a Next 16 packaging detail and do not resolve on 15.
- `tsconfig.json` — `next build` rewrote `jsx` from `react-jsx` to
  `preserve`, which is what Next 15 wants.

### Things to be honest about

- **The tracker gives up Next 16.** The alternative — upgrading the
  backoffice to 16 — unifies forward instead and keeps the newer
  framework, but it means a major upgrade of the primary app (auth,
  incident manager, suppliers, analyzer) to fix a build in a secondary
  one. That trade is available if the team would rather go forward; the
  change would be the same three edits in the opposite direction.
- **The tracker's 5 eslint errors disappeared without the code changing.**
  They were `react-hooks` "setState synchronously within an effect"
  violations, and that rule ships with `eslint-config-next@16`. On 15 the
  rule does not run. The patterns are still in the code. Verified eslint
  is genuinely checking these files by planting a violation and watching
  it get caught.
- `overrides` was tried first and npm 11.12.1 silently ignored it — it
  never appeared in the lockfile, even after regenerating from scratch.

### Verification

- `npm run build` exit 0, **all three** Next apps compile — the tracker
  produces all 6 routes.
- `npm run typecheck` exit 0 across 5 workspaces; `npm run test` 64
  passing; 286 backend tests; ruff and eslint clean.
- A passing build is not a working app, so both were driven in a browser:
  the tracker renders, and a controlled input updates (proving there is
  one React instance and hooks work — the duplicate-React failure showed
  up precisely as `Cannot read properties of null (reading 'useContext')`
  during prerender). The backoffice's 56 error-handling assertions and the
  supplier directory check were re-run against the shared hoisted React.

## 2026-08-28 — Portable Linux native dependencies

- GitHub Actions exposed npm's cross-platform optional-dependency lockfile
  bug during clean Ubuntu installs. The root now declares the exact Linux
  x64 native packages used by Lightning CSS and Tailwind CSS Oxide so
  `npm ci` installs both bindings deterministically on the CI runner.

## 2026-08-28 — Inventory backoffice

- Added protected inventory routes to the existing backoffice for the SKU
  list, goods receipts, dispatches/losses, and the unified movement audit.
- All inventory HTTP calls live in `uis/backoffice/lib/inventory.ts` and use
  the shared bearer-token client. Components never call `fetch` directly.
- Product stock is visibly warehouse-scoped and computed by the API. The UI
  flags out-of-stock and low-stock SKUs, previews available stock before an
  exit, and blocks obvious oversells while preserving the API as the final
  concurrency-safe authority.
- Dispatches require a tracking number; warehouse losses omit one, matching
  the TrackFlow inventory rules. Movement rows show product, warehouse,
  reference/tracking data, and the authenticated user identifier.
- Added the stable `milestone-5-inventory-backoffice` submission snapshot to
  `MILESTONES.md`; the existing Inventory ORM milestone remains separate.

## 2026-08-28 — Company monorepo containerization

- Added a Node Alpine UI image and `uis/start.sh` to run the website on 3000
  and backoffice on 3001 from the shared npm workspace installation.
- Added a Python 3.12 service image that installs `uv`, consumes
  `services/requirements.txt`, and runs the centralized FastAPI app through
  Uvicorn with reload enabled.
- Root Compose now starts both services on a named network, waits for the API
  health check, bind-mounts source for hot reload, and retains dependencies
  and development data in named volumes.
- Added scoped Docker ignore files and a safe `.env.example`; the real root
  `.env` remains gitignored. SQLite is the credential-free local inventory
  default, while Supabase can be selected through an uncommitted value.
- Docker was not installed on the authoring machine, so image execution was
  not claimed. Static Dockerfile/Compose validation and the full repository
  typecheck, test, and build workflow are the available verification gates.

## 2026-08-29 — Warehouse Steward acceptance proof

- Added the dedicated public OpenClaw workspace under `.openclaw/`: Warehouse
  Steward identity, six hard safety constraints, authenticated HTTP-only tool
  contract, read-only `stock-check`, confirmation-gated `log-movement`, and a
  shared Node adapter that never logs credentials or retries writes.
- Registered the isolated `trackflow-warehouse` agent and verified the existing
  OpenAI runtime with a real embedded turn. Private operative credentials stay
  only in ignored `.openclaw/.env`; no bearer token is persisted.
- Ran the documented seed command against the Docker API. That exposed three
  real packaging omissions (`seed_inventory`, `routers*`, and `schemas`) in
  `services/api/pyproject.toml`; fixed them and added regression tests for all
  console-script imports.
- Captured `.openclaw/TRANSCRIPT.md` from a real session: two white-sneaker
  candidates were disambiguated, LA stock was freshly read as 145, a separately
  confirmed 60-unit receipt produced movement 6 and stock 205, a declined loss
  wrote nothing, and a 999-unit dispatch returned the API's exact HTTP 400
  insufficient-stock message without a retry.
- Independently checked the movement feed after the conversation: one matching
  receipt exists, no declined serum loss exists, no refused tracking number
  exists, and LA stock remains 205.

## 2026-08-29 — Talent Pipeline consolidated into backoffice

- Added a protected `Talent pipeline` section to the existing backoffice at
  `/talent`, with the full Milestone 3 list/search/filter, register, detail,
  edit, stage/status update, and internal-note workflows.
- Kept candidate traffic isolated behind `lib/talent-api.ts` and a same-origin
  `/talent-api` rewrite; it does not reuse the authenticated TrackFlow
  inventory/auth base URL or depend on cross-origin browser policy.
- Added focused tests for API URL normalization and candidate filter query
  construction. Backoffice typecheck, 49 tests, and lint pass.
- Preserved `milestone-3-talent-pipeline` and the historical standalone
  workspace as assessment evidence while making the cumulative backoffice the
  single current demo surface.
