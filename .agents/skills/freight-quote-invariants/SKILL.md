---
name: freight-quote-invariants
description: Verify that the freight-quote implementation and every UI that renders quotes still honours the invariants declared in CONTEXT.md. Use when adding a Service tier, changing pricing, introducing a new currency, or before merging any change under packages/business-logic or uis/backoffice.
license: MIT
metadata:
  author: armonon
  version: "1.0.0"
  project: trackflow-monorepo
---

# Freight-quote invariants — verification skill

## Objective

Confirm that `packages/business-logic/src/freight-quote.ts` and every
caller in `uis/**` obeys the freight-quote invariants declared in
[`CONTEXT.md`](../../../CONTEXT.md). One objective, one artifact
(the exit code of `scripts/verify.mjs`).

## Inputs

The skill needs nothing from the requester beyond a working
repository at HEAD. It reads:

- `CONTEXT.md` — the source of truth for the invariants.
- `packages/business-logic/src/freight-quote.ts` — implementation
  under test.
- `packages/business-logic/dist/*` — must exist. If it doesn't, the
  script fails fast with `npm run bootstrap` as the remedy.

## Expected output

- Exit code `0` and a single line to stdout:
  `freight-quote-invariants: OK (N assertions)`.
- Any failure prints the offending assertion, expected vs. actual,
  and the line in `CONTEXT.md` that the assertion enforces. Exit
  code `1`.

## Invariants asserted (locked to CONTEXT.md)

The script currently asserts these — extend it, don't work around it.

1. **Currency by country.** `country: "US"` → `currency: "USD"`;
   `country: "ES"` → `currency: "EUR"`. An ES quote is never `"USD"`
   or `"$"`.
2. **Priority service tier eligibility.** `serviceTier: "priority"`
   accepted only when both `originZone` and `destinationZone` are
   `"metro"`, in either served country. Any other combination throws
   with a message that names the failing precondition.
3. **Weight and distance floors.** `weightKg > 0` and
   `distanceKm > 0`. Zero or negative → thrown error, not a silent
   zero-quote.
4. **Deterministic pricing.** For a frozen input, `quoteShipment`
   returns the same object shape and same numeric total across two
   consecutive calls (`totalPrice`, `currency`, `serviceTier`,
   `breakdown.base`, `breakdown.distance`, `breakdown.weight`).
5. **Rounding.** `totalPrice` is rounded to 2 decimals. No
   floating-point drift like `123.4500000001`.

## How to run

```bash
node .agents/skills/freight-quote-invariants/scripts/verify.mjs
```

or via the workspace alias:

```bash
npm run verify:freight-quote
```

## Acceptance criteria (checklist)

- [ ] `node ...scripts/verify.mjs` exits `0`.
- [ ] Output line matches `freight-quote-invariants: OK (\d+ assertions)`.
- [ ] Adding a **new** invariant to CONTEXT.md is followed, in the
      same PR, by a matching assertion in `scripts/verify.mjs`. If
      the invariant is added without an assertion, the reviewer
      blocks the PR — a rule without a check is decorative.
- [ ] The script has zero runtime dependencies outside Node's stdlib
      (`node:assert`, `node:test`, dynamic `import`). It must run
      on a bare Codespace with no `npm install` beyond the workspace
      bootstrap.
- [ ] When the script fails, its message names both the CONTEXT.md
      section and the code path that diverged — the point is to
      make the fix obvious, not to signal that "something's off".

## Anti-patterns to reject

- Duplicating any invariant check in `uis/backoffice`. The UI
  consumes `quoteShipment`; the invariant lives here.
- Bypassing the skill with a hand-run test when adding a new
  invariant. If the invariant is real, it belongs in
  `scripts/verify.mjs` so future agents pick it up automatically.
- Adding new currency codes without also extending assertion (1).
