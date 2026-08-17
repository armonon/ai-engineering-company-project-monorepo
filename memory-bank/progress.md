# Progress — TrackFlow monorepo

Rolling log of substantive changes. Newest first.

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

---

## Milestone 5 — inventory with SQLModel and a second database

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
