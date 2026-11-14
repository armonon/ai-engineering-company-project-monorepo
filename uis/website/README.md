# `uis/website` — TrackFlow public site

The public-facing TrackFlow site: Next.js 16 (App Router), TypeScript
strict, Tailwind v4.

It is the **Milestone 1 static site migrated to Next.js**, not a rewrite.
Every section of `uis/public-website/index.html` is carried over with its
original anchor and copy, and the information-request page comes with it.

## Routes

| Route | What it is |
| --- | --- |
| `/` | Landing page: `#home`, `#services`, `#coverage`, `#why`, `#contact` — the five Milestone 1 sections — plus the service-tier section added in Milestone 4. |
| `/application` | The information-request form, migrated from `application.html` + `validation.js`. |

## What the migration preserves

- **Anchors and copy.** The nav links `/#home`, `/#services`, `/#coverage`,
  `/#why`, `/#contact`; carriers, warehouses, phone numbers and the
  "Why TrackFlow" claims are the briefing's wording.
- **Structured data.** The Schema.org `Organization` block (founding date,
  both postal addresses, sales contact point, areas served) is emitted from
  `app/layout.tsx`.
- **Accessibility.** Skip link, `#main` landmark, labelled
  `Main navigation`, and per-field error text tied to each control with
  `aria-describedby` / `aria-invalid`.
- **Form rules.** `lib/applicationValidation.ts` holds the briefing's exact
  error messages, option values, 500-character comment limit, and the
  low-volume warning that warns without blocking submission.

## Commands

Run these from the **repository root** — the workspace is linked there:

```bash
npm install          # once, from the root
npm run dev:website  # http://localhost:3000
```

```bash
npm run lint --workspace @trackflow/website
npm run typecheck --workspace @trackflow/website
npm run test --workspace @trackflow/website   # 17 tests
```

`npm test` compiles `lib/` and `tests/` to `.test-dist/` with
`tsconfig.test.json` and runs them under `node --test`. Ten tests re-assert
the Milestone 1 form rules; six fail if the migration ever drops a section,
an anchor, a copy string, the structured data, or an accessibility
affordance.
