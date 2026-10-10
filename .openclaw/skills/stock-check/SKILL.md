---
name: stock-check
description: Resolve a spoken product description or SKU to real TrackFlow inventory and report freshly read stock for the requested LA or ZGZ warehouse. Use for stock, availability, low-stock, and product-location questions.
metadata:
  {
    "openclaw":
      {
        "emoji": "🔎",
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

# Stock check

Read-only skill for resolving a product to a real SKU and reporting current,
warehouse-scoped stock.

## Endpoints

- `GET /inventory/products`
- `GET /inventory/products/{id}`

This skill never calls an inventory `POST`.

## Procedure

1. Extract the requested description or SKU and warehouse (`LA` or `ZGZ`). If
   the warehouse is missing and the product may exist in both, do not assume
   one.
2. Search the live product list:

   ```bash
   node skills/_shared/inventory-api.mjs products \
     --query "<description or SKU>" [--warehouse LA|ZGZ]
   ```

3. Resolve only from returned candidates:
   - Zero matches: say no matching SKU was returned and ask for another code or
     description.
   - One match: continue.
   - Multiple matches: show each exact SKU code, name, warehouse, and freshly
     returned stock; ask the operative to choose. Do not rank or choose for
     them.
4. After the SKU is unambiguous, re-read it immediately:

   ```bash
   node skills/_shared/inventory-api.mjs product --id <real id>
   ```

5. Answer with exact SKU code, product name, warehouse, and `current_stock`.
   Say that the figure was read just now.

For “what is low” questions, list live products in the named warehouse and
report all SKUs at or below the quantity the user supplied. If they supplied
no threshold, say that low stock needs a threshold instead of inventing one.

## Refusals

- Never estimate stock from an earlier turn.
- Never combine LA and ZGZ quantities.
- Never invent, normalize, or repair a SKU code.
- Never expose another client's stock beyond what the authenticated API
  returns.
- Never use a database, file, or Docker command to answer a stock question.
