# `uis/backoffice` — TrackFlow internal app

The internal operations app for TrackFlow staff: Next.js 16 (App Router),
TypeScript strict, Tailwind v4.

It renders domain output; it does not own domain rules. Both screens import
the package that owns the logic, which is what rule **MONO-1** requires.

## Routes

| Route | Renders | Owned by |
| --- | --- | --- |
| `/` | Inventory operations — stock ordered lowest-first, low-stock detection, warehouse split, inventory value, product validation, and carrier selection for the sample shipment. | `@trackflow/programming-fundamentals` (Milestone 2) |
| `/freight-quote` | Live freight quote with the cost breakdown. | `@trackflow/business-logic` |

### `/` — inventory operations

Every figure is computed at render time by the Milestone 2 module:
`sortProductsByStock`, `filterLowStockProducts`,
`filterProductsByWarehouse`, `calculateTotalInventoryValue`,
`countProductsByCategory`, `findProductBySKU`, `validateProduct`,
`validateShipment`, `scoreCarrierForShipment`, `calculateShippingCost`,
`selectBestCarrier` and `sortCarriersByReliability`. Nothing is
re-implemented or copied here.

The carrier panel shows the module's output unmodified, including a case
worth knowing about: `selectBestCarrier` scores destination coverage (+20)
but does not require it, then takes the cheapest carrier above the score
threshold — so it can return a carrier that does not operate in the
destination country. The screen labels that rather than hiding it.
Dispatch would need a coverage filter before acting on the result.

### `/freight-quote`

`quoteShipment()` from `@trackflow/business-logic` — the package the
Milestone 4 skill checks. Run `npm run verify:freight-quote` from the
repository root to assert its invariants.

## Commands

Run these from the **repository root** — the workspace is linked there:

```bash
npm install             # once, from the root
npm run bootstrap       # compile both packages first
npm run dev:backoffice  # http://localhost:3100
```

Skipping `bootstrap` fails with
`Module not found: Can't resolve '@trackflow/programming-fundamentals'`.
