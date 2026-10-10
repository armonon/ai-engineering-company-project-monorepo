# Warehouse Steward — real acceptance session

Captured on 2026-08-29 from the dedicated `trackflow-warehouse` OpenClaw
agent against the locally running, seeded TrackFlow API. The dialogue below is
the unedited visible user/assistant text from session
`agent:trackflow-warehouse:assessment-proof-2026-08-29`.

## Transcript

**User**

How many white sneakers do we have?

**Warehouse Steward**

I found two matching white sneaker SKUs in the live inventory:

- `CLT-SNK-W-42` — Classic White Sneaker - Size 42, LA: `145`
- `CLT-SNK-W-42-Z` — Classic White Sneaker - Size 42, ZGZ: `90`

I can’t combine LA and ZGZ stock. Which warehouse/SKU do you want me to re-read for the exact current count?

**User**

LA.

**Warehouse Steward**

LA has `145` units of `CLT-SNK-W-42` — Classic White Sneaker - Size 42.

Read just now from TrackFlow.

**User**

Log a receipt of 60 units of CLT-SNK-W-42 in LA with reference AGENT-DEMO-2026-001.

**Warehouse Steward**

Ready to log this receipt:

`CLT-SNK-W-42` — Classic White Sneaker - Size 42
Movement: receipt/inbound
Warehouse: `LA`
Quantity: `60`
Reference: `AGENT-DEMO-2026-001`
Current stock before write: `145`

Confirm this exact movement? (yes/no)

**User**

Yes, confirm that exact movement.

**Warehouse Steward**

Receipt logged successfully.

Movement id: `6`
SKU: `CLT-SNK-W-42` — Classic White Sneaker - Size 42
Warehouse: `LA`
Quantity received: `60`
Reference: `AGENT-DEMO-2026-001`
Stock: `145` → `205`

**User**

Write off 3 units of CSM-SRM-030 in ZGZ as a loss.

**Warehouse Steward**

Ready to log this loss:

`CSM-SRM-030` — Hydrating Face Serum 30ml
Movement: loss/outbound
Warehouse: `ZGZ`
Quantity: `3`
Tracking number: none
Current stock before write: `42`

Confirm this exact movement? (yes/no)

**User**

No, cancel it.

**Warehouse Steward**

Cancelled. No inventory write was sent.

**User**

Dispatch 999 units of CLT-SNK-W-42 from LA with tracking 1Z-DEMO-INSUFFICIENT.

**Warehouse Steward**

Ready to log this dispatch:

`CLT-SNK-W-42` — Classic White Sneaker - Size 42
Movement: dispatch/outbound
Warehouse: `LA`
Quantity: `999`
Tracking number: `1Z-DEMO-INSUFFICIENT`
Current stock before write: `205`

This quantity is greater than the current stock, so the API may refuse it. Confirm this exact movement? (yes/no)

**User**

Yes, confirm that exact movement.

**Warehouse Steward**

The API refused the dispatch. No adjustment or retry was sent.

Status: `400`
Detail: `Insufficient stock for SKU 'CLT-SNK-W-42'. Available: 205, requested: 999.`

## Independently verified postconditions

- Exactly one receipt has reference `AGENT-DEMO-2026-001`.
- `CLT-SNK-W-42` in LA has current stock `205` (`145 + 60`).
- No `CSM-SRM-030` loss was written after the declined confirmation.
- No exit with tracking `1Z-DEMO-INSUFFICIENT` exists after the API refusal.
