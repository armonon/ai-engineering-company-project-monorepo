# `@trackflow/programming-fundamentals`

Milestone 2 module — domain types and pure utility functions for
TrackFlow's Product / Shipment / Carrier / InventoryMovement
domain.

## Contents

- `src/types/models.ts` — `Product`, `Shipment`, `Carrier`,
  `InventoryMovement`, and supporting enums.
- `src/utils/collections.ts` — non-mutating filters and sorts.
- `src/utils/search.ts` — linear and binary search helpers.
- `src/utils/transformations.ts` — shipping cost, carrier scoring,
  carrier selection, category/inventory/distance/status/carrier
  aggregations.
- `src/utils/validations.ts` — Product / Shipment / Carrier
  business-rule validations.
- `src/data/sampleData.ts` — official TrackFlow sample dataset.
- `src/demo.ts` — runnable end-to-end walkthrough.

Everything is re-exported from `src/index.ts` for consumers.

## Relationship to other packages

Distinct from `@trackflow/business-logic` (Milestone 4), which owns
the freight-quote formula only. This package is the broader
domain-model foundation the M2 rubric asked for; freight-quote is
one narrow slice that grew into its own workspace when it needed
to be consumed by UIs (rule `MONO-1`).

## Commands

```bash
npm run build      # tsc → dist/
npm run typecheck  # tsc --noEmit
npm run test       # node --test on compiled tests (24 tests)
npm run demo       # runs src/demo.ts against sampleData
```
