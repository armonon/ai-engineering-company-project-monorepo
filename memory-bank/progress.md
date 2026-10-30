# Progress — TrackFlow monorepo

Rolling log of substantive changes. Newest first.

---

## 2026-10-30 · Milestone 1 resubmission: official TrackFlow briefing

- Added the official briefing as root `BRIEFING.md` and
  `docs/company-context/00–01` (verbatim from 4GeeksAcademy/ai-engineering-syllabus).
- Added `uis/public-website/` — the Milestone 1 deliverable built from the
  official briefing: `index.html`, `application.html`, `validation.js`,
  compiled Tailwind, Schema.org, all 12 form fields with the exact messages.
  Run: `npx --yes http-server@14.1.1 uis/public-website -p 3000 -a 0.0.0.0 -c-1`.
  Lighthouse (mobile) 92/100/100/100 and 99/100/100/100; 12 Node tests.
- Realigned the snapshot from Mexico/MXN to United States/USD (CONTEXT,
  freight quote with official UPS sample rates, website copy, memory bank) and
  upgraded the Next.js site to 16.4.3 (security advisories; audit clean).

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

### Notes on rebuilds vs. migrations

The public website's Milestone 1 version and the Milestone 2
TypeScript module are not present in the fork at the start of this
milestone. Both were **built from CONTEXT.md** so this delivery is
self-contained and reflects TrackFlow rather than a generic company.
When earlier milestones land, `MONO-1` (single source of truth) is
the guardrail that keeps the imports pointed at
`packages/business-logic`.
