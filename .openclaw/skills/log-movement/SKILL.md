---
name: log-movement
description: Register an authenticated TrackFlow receipt, dispatch, or loss only after resolving the exact SKU and obtaining a separate explicit confirmation. Use when stock is arriving, shipping, damaged, missing, or being written off.
metadata:
  {
    "openclaw":
      {
        "emoji": "📝",
        "requires":
          {
            "bins": ["node"],
            "env":
              [
                "TRACKFLOW_API_ORIGIN",
                "TRACKFLOW_API_EMAIL",
                "TRACKFLOW_API_PASSWORD",
              ],
          },
      },
  }
---

# Log movement

Write skill for authenticated receipts, dispatches, and losses.

## Endpoints

- Resolve and read: `GET /inventory/products`,
  `GET /inventory/products/{id}`
- Write: `POST /inventory/orders/inbound`,
  `POST /inventory/orders/outbound`
- Verify: `GET /inventory/products/{id}`, `GET /inventory/orders`

## Required fields

- Receipt: SKU, quantity, reference, warehouse.
- Dispatch: SKU, quantity, tracking number, warehouse.
- Loss: SKU, quantity, warehouse; tracking number must be absent.

Quantity must be a positive integer. Never fill a missing field by guessing.

## Procedure

1. Resolve the product with the live product list exactly as `stock-check`
   does. Ambiguity stops the flow until the user chooses an exact candidate.
2. Re-read the selected SKU immediately and record its current stock.
3. Build a confirmation sentence containing every material value:
   - exact SKU code and product name
   - quantity
   - `LA` or `ZGZ`
   - receipt, dispatch, or loss
   - reference for a receipt, or tracking number for a dispatch
   - current stock before the proposed write
4. Ask: `Confirm this exact movement? (yes/no)` and stop. The original request
   is not confirmation. Only a subsequent explicit yes permits step 5.
5. After yes, call exactly one write command:

   Receipt:

   ```bash
   node skills/_shared/inventory-api.mjs inbound \
     --sku-id <id> --sku-code <exact code> --quantity <integer> \
     --reference <reference> --warehouse <LA|ZGZ> --confirmed
   ```

   Dispatch:

   ```bash
   node skills/_shared/inventory-api.mjs outbound \
     --sku-id <id> --sku-code <exact code> --quantity <integer> \
     --exit-type dispatch --tracking-number <tracking> \
     --warehouse <LA|ZGZ> --confirmed
   ```

   Loss:

   ```bash
   node skills/_shared/inventory-api.mjs outbound \
     --sku-id <id> --sku-code <exact code> --quantity <integer> \
     --exit-type loss --warehouse <LA|ZGZ> --confirmed
   ```

6. Interpret the result once:
   - Exit `0`: re-read the exact SKU, then report the API-created movement id,
     prior stock, quantity, and freshly read final stock.
   - Exit `2`: relay the API refusal and stop. Do not adjust or retry.
   - Exit `3`: say the outcome is unknown and stop. Tell the operative to
     inspect the movement feed; do not retry.
   - Exit `64`: no write occurred. Correct the local validation problem and
     return to confirmation before any later write.

If the user says no or anything that is not an explicit yes, say the movement
was cancelled and do not invoke the write command. A read-only movement-feed
check is allowed when the user asks for verification.

## Refusals

- Never send a write before a separate confirmation turn.
- Never retry a timeout, disconnect, server error, or refused movement.
- Never split or shrink an insufficient-stock dispatch.
- Never switch warehouses or SKU codes to make a write succeed.
- Never send `user_uuid`, `created_at`, or a stock value in a request.
- Never create a SKU or access a database directly.
