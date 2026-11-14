# TrackFlow — Milestone 4: AI-assisted engineering

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Submission snapshot for the AI Engineering Career Program — 4Geeks Academy._

_Estas instrucciones tambien estan disponibles en [espanol](./README.es.md)._

This branch is the **Milestone 4 submission snapshot** of the TrackFlow
monorepo. The assigned company is **TrackFlow**, a last-mile delivery and
warehousing operator working out of Los Angeles and Zaragoza.

---

## What this milestone delivers

Milestone 4 is about making the repository **AI-assisted**: giving an agent
(and a human) the context, rules, and reusable capabilities needed to work in
this codebase without guessing. Four layers of guidance, plus the two
front-ends that consume them.

| Deliverable | Path | What it is |
| --- | --- | --- |
| Company context | [`CONTEXT.md`](./CONTEXT.md) | Single source of truth for the TrackFlow domain — entities, field names, validation rules, constraints. Everything built here must agree with it. |
| Company briefing | [`BRIEFING.md`](./BRIEFING.md) | The official 4Geeks TrackFlow briefing: departments, stakeholders, technology gaps, milestone roadmap. |
| Agent rules | [`AGENTS.md`](./AGENTS.md) | The mandatory delivery workflow, what may not be changed without confirmation, and the reading order for any contributor. |
| Memory bank | [`memory-bank/`](./memory-bank) | `projectbrief.md`, `techContext.md`, and `progress.md` — the durable record an agent reads to recover context between sessions. |
| Conventions rule | [`.agents/rules/monorepo-conventions.md`](./.agents/rules/monorepo-conventions.md) | Where code belongs in this monorepo and why. |
| Executable skill | [`.agents/skills/freight-quote-invariants/`](./.agents/skills/freight-quote-invariants) | A skill with a **runnable verifier** (`scripts/verify.mjs`) that asserts the freight-quote business rules. It is not prose — it fails the build when an invariant breaks. |
| Milestone 2 module | [`packages/programming-fundamentals/`](./packages/programming-fundamentals) | `@trackflow/programming-fundamentals` — the real Milestone 2 output: `Product`, `Shipment`, `Carrier` and `InventoryMovement` types with collection filters, searches, transformations, and validations. |
| Business logic | [`packages/business-logic/`](./packages/business-logic) | `@trackflow/business-logic` — the freight-quote calculation the Milestone 4 skill verifies. |
| Public website | [`uis/website/`](./uis/website) | TrackFlow's public corporate site (Next.js 16, App Router) — the full migration of the Milestone 1 static site, plus the information-request form. |
| Backoffice | [`uis/backoffice/`](./uis/backoffice) | The internal operations app. Its home screen renders `@trackflow/programming-fundamentals` output; `/freight-quote` runs the skill-verified quote calculation. |

`services/` contains only its folder README at this milestone — the FastAPI
backend arrives in Milestone 5. That is deliberate, not an omission.

### What the apps consume

Neither app re-implements a domain rule; both import the package that owns
it, which is what rule **MONO-1** requires:

- **Backoffice home (`/`)** — stock ordering, low-stock detection, the
  warehouse split, inventory value, product validation, and carrier
  selection are all computed at render time by
  `@trackflow/programming-fundamentals`.
- **Backoffice `/freight-quote`** — `quoteShipment()` from
  `@trackflow/business-logic`, the package `npm run verify:freight-quote`
  checks.
- **Website** — every section of the Milestone 1 static site (`home`,
  `services`, `coverage`, `why`, `contact`) with its anchor and content,
  the Schema.org `Organization` data, the skip link, and the
  information-request form at `/application` with the briefing's exact
  validation messages and option values.

---

## Running it after a fresh clone

**Order matters.** Both front-ends import `@trackflow/business-logic`, a
workspace package whose compiled `dist/` is git-ignored. Building or running a
UI before that package is linked and compiled fails with
`Module not found: Can't resolve '@trackflow/business-logic'`.

```bash
# 1. From the REPO ROOT — links the npm workspaces
npm install

# 2. From the REPO ROOT — compiles packages/*/dist
npm run bootstrap
```

Only then are the UIs runnable:

```bash
npm run dev:website       # http://localhost:3000
npm run dev:backoffice    # http://localhost:3100
```

> Running `npm install` *inside* `uis/backoffice` alone is not enough — npm
> workspaces are linked from the repository root.

Requires Node.js 20 or newer (`engines.node` in the root `package.json`).

---

## Verifying the milestone

Every command below is expected to pass on a clean clone of this branch:

```bash
npm ci                      # install from the committed lockfile
npm run bootstrap           # compile the workspace package
npm run typecheck           # tsc --noEmit across all three workspaces
npm test                    # 48 tests across all workspaces
npm run build               # production build of both Next.js apps
npm run verify:freight-quote    # the skill's own invariant verifier
```

`npm run verify:freight-quote` is the one worth looking at: it is the
executable half of the freight-quote skill, and it asserts the invariants
`CONTEXT.md` states, directly against `@trackflow/business-logic` —

1. **Currency by country** — `US` quotes in USD, `ES` quotes in EUR, and a
   Spanish quote is never priced in USD or `$`.
2. **Priority-tier eligibility** — allowed only metro→metro, in both
   countries, and rejected when either zone is not metro.
3. **Weight and distance floors** — a non-positive `weightKg` or `distanceKm`
   is rejected rather than silently quoted.
4. **Deterministic pricing** — the same input returns an identical quote.
5. **Rounding** — `totalPrice` carries no floating-point drift past 2 decimals.

It prints `freight-quote-invariants: OK (10 assertions)` while the
implementation still honours that contract, and exits non-zero naming the
broken invariant when it does not.

`npm test` covers all three suites: 7 freight-quote tests, 24
programming-fundamentals tests, and 17 website tests — 10 of which re-assert
the Milestone 1 form rules after the migration, while 6 fail if the Next.js
site ever drops a Milestone 1 section, its anchor, its content, or its
structured data.

---

## How to think about this monorepo

One company, many milestones. Each top-level folder has a single
responsibility, like a real engineering team repo.

| Layer | Folders | What lives here |
| --- | --- | --- |
| **Company context** | `CONTEXT.md` | Domain facts, field names, constraints for TrackFlow |
| **User-facing** | `uis/`, `services/` | Frontends and backends users (or operators) interact with |
| **Data** | `data/` | Raw files, pipelines, processed datasets, evaluation sets |
| **AI** | `agents/`, `skills/`, `mcps/` | Agents, reusable agent capabilities, MCP tool servers |
| **Automation** | `workflows/` | n8n flows and cross-system orchestration |
| **Reuse** | `packages/`, `shared/` | Shared types, SDKs, schemas, templates |
| **Operations** | `infra/`, `scripts/`, `internal/` | Docker, deploy configs, one-off scripts, internal CLIs |
| **Documentation** | `docs/` | Architecture, decisions, conventions for the whole repo |

**Rule of thumb:** if it has a UI → `uis/`. If it exposes an API or runs in the
background → `services/`. If it moves or transforms data → `data/`. If an AI
model does the work → `agents/` (+ `skills/` or `mcps/` as needed).

---

## Where this branch sits

This repository stays cumulative on `main`; each milestone branch is a stable
submission snapshot taken from it. `main` has since grown a FastAPI backend,
authentication, inventory, incident analysis, supplier management, and
telemetry — none of which belong to this milestone. Read this branch to review
Milestone 4 as submitted; read `main` for the current state of TrackFlow.

Working rules for milestone branches are in [`AGENTS.md`](./AGENTS.md).
