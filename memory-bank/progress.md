# Progress — TrackFlow monorepo

Rolling log of substantive changes. Newest first.

---

## 2026-10-30 · Milestone 4 resubmission: official TrackFlow briefing

- Added the official briefing as root `BRIEFING.md`; realigned CONTEXT,
  freight quote (US/USD with the official Milestone 2 UPS sample rates;
  priority metro→metro in either country), invariant skill, backoffice quote
  calculator, website copy, and memory bank from Mexico/MXN to the United
  States/USD. Upgraded Next.js to 16.4.3 (security advisories; audit clean).

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
