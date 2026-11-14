# Progress — TrackFlow monorepo

Rolling log of substantive changes. Newest first.

---

## 2026-11-13 · Milestone 4 — second resubmission after review

**Branch:** `milestone-4`

The reviewer accepted the memory bank, contributor workflow, scoped rule,
skill, and the separate apps, and rejected two things. Both are fixed here.

### 1. The backoffice ran a stand-in instead of the real Milestone 2 output

The original delivery predated Milestones 1-3 landing in the repository, so
it built `packages/business-logic` as a "Milestone 2 stand-in" and the
backoffice home rendered its freight-quote form. The real Milestone 2
module existed on `milestone-2-fold-in` and was never wired in.

- `packages/programming-fundamentals/` is now part of this branch, with its
  24 tests.
- The backoffice home renders **its** output — stock ordering, low-stock
  detection, warehouse split, inventory value, product validation, and
  carrier selection — computed at render time by `sortProductsByStock`,
  `filterLowStockProducts`, `filterProductsByWarehouse`,
  `calculateTotalInventoryValue`, `validateProduct`, `validateShipment`,
  `findProductBySKU`, `selectBestCarrier`, `calculateShippingCost` and
  `sortCarriersByReliability`. Nothing is re-implemented (MONO-1).
- The freight-quote calculator moved to `/freight-quote`. It stays because
  `@trackflow/business-logic` is what the Milestone 4 skill verifies —
  removing it would remove the skill's subject.
- Root `bootstrap` builds both packages; root `test` now runs every
  workspace instead of one package.

**Observed while wiring it up, not changed:** for the sample Spain
shipment, `selectBestCarrier` returns UPS, which lists only the United
States. `scoreCarrierForShipment` awards +20 for destination coverage but
`selectBestCarrier` only requires score >= 50 and then takes the cheapest,
so an uncovered carrier can win. That is Milestone 2's logic, already
accepted; this milestone renders it unmodified and labels the gap in the UI
rather than silently patching another milestone's package. Worth raising as
a Milestone 2 follow-up.

### 2. The public site dropped sections from the Milestone 1 static site

The Next.js site had been rebuilt from `CONTEXT.md` rather than migrated,
so it carried `offering`, `countries`, `pricing` and `contact` and had lost
the static site's `home`, `services`, `coverage` and `why` anchors, their
content, the structured data, and the whole information-request page.

- `uis/website/app/page.tsx` now carries every Milestone 1 section with its
  original anchor and content: `home`, `services`, `coverage`, `why`,
  `contact`. The service-tier section is kept as this milestone's addition.
- `uis/website/app/layout.tsx` restores the skip link, the
  `Main navigation` landmark linking all five anchors, the footer, the
  Milestone 1 metadata, and the Schema.org `Organization` block.
- `application.html` + `validation.js` are migrated to `/application` plus
  `lib/applicationValidation.ts`. Messages, option values, the
  500-character comment limit, and the non-blocking low-volume warning are
  carried over verbatim from the briefing.
- 17 website tests added: 10 re-assert the Milestone 1 form rules after the
  migration, 6 fail if a section, anchor, content string, structured-data
  field, or accessibility affordance is dropped again, and 1 checks the
  form stays reachable. Checked against the rejected revision — all 6
  migration guards fail on it.

### Also

- The root `README.md` was still the unmodified 4Geeks student template,
  stating the repo had no runnable apps, no `AGENTS.md`, and a placeholder
  `CONTEXT.md` — all false. Replaced with the milestone's own README.
- Removed `uis/website/components/FeatureCard.tsx`, unused after the
  migration.

### Verification

`npm ci`, `npm run bootstrap`, `npm run typecheck`, `npm test` (48 tests:
7 + 24 + 17), `npm run build`, `npm run verify:freight-quote`
(10 assertions) all pass from a clean clone. Both apps were driven in a
browser: every Milestone 1 section renders, the form shows the briefing's
errors on empty submit, warns on 0-100 volume without blocking, and reaches
the thank-you state; the backoffice renders real Milestone 2 figures and
`/freight-quote` still quotes.

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
