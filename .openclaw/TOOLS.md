# Warehouse Steward tools

## TrackFlow inventory API

- API origin comes from `TRACKFLOW_API_ORIGIN`.
- Authentication comes from `TRACKFLOW_API_EMAIL` and
  `TRACKFLOW_API_PASSWORD` in the ignored workspace `.env` file.
- The helper logs in through `POST /auth/login`, keeps the resulting bearer
  token in process memory, and never prints credentials or the token.
- All inventory routes are authenticated.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/inventory/products` | List SKUs with current per-warehouse stock. |
| `GET` | `/inventory/products/{id}` | Re-read one exact SKU and its current stock. |
| `POST` | `/inventory/orders/inbound` | Record a confirmed goods receipt. |
| `POST` | `/inventory/orders/outbound` | Record a confirmed dispatch or loss. |
| `GET` | `/inventory/orders` | Read the movement feed, newest first. |

The agent never calls `POST /inventory/products` and never accesses the
database directly.

## Safe command adapter

Each skill invokes the shared adapter from the warehouse workspace root:

```bash
node skills/_shared/inventory-api.mjs <command> [options]
```

Supported read commands:

```bash
node skills/_shared/inventory-api.mjs products --query "white sneaker" --warehouse LA
node skills/_shared/inventory-api.mjs product --id 1
node skills/_shared/inventory-api.mjs movements --warehouse LA
```

Supported write commands require `--confirmed` and an exact SKU id/code pair:

```bash
node skills/_shared/inventory-api.mjs inbound \
  --sku-id 1 --sku-code CLT-SNK-W-42 --quantity 60 \
  --reference PO-2024-0098 --warehouse LA --confirmed

node skills/_shared/inventory-api.mjs outbound \
  --sku-id 1 --sku-code CLT-SNK-W-42 --quantity 12 \
  --exit-type dispatch --tracking-number 1Z999AA10123456784 \
  --warehouse LA --confirmed
```

For a loss, use `--exit-type loss` and omit `--tracking-number`.

Exit codes:

- `0` — request succeeded.
- `1` — authentication or read failed.
- `2` — the API refused a write; relay its response and do not retry.
- `3` — write outcome unknown; inspect the feed and do not retry.
- `64` — local validation stopped the request before any inventory write.
