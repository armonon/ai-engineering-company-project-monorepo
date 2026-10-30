# `@trackflow/business-logic`

Authoritative TrackFlow domain logic (Milestone 2 module). Currently
exposes the freight-quote calculator.

## Public API

```ts
import { quoteShipment, currencyForCountry } from "@trackflow/business-logic";
```

- `quoteShipment(input)` → `QuoteResult`. Throws on invalid input.
- `currencyForCountry(country)` → `"USD" | "EUR"`.
- `isPriorityEligible(input)` → `boolean`.

Types: `Country`, `Zone`, `ServiceTier`, `Currency`, `QuoteInput`,
`QuoteResult`, `QuoteBreakdown`.

## Rules

Read [`.agents/rules/monorepo-conventions.md`](../../.agents/rules/monorepo-conventions.md)
— specifically `MONO-1` — before editing this package.

## Commands

```bash
npm run build      # tsc → dist/
npm run typecheck  # tsc --noEmit
npm run test       # node --test on compiled tests
```
