# TrackFlow telemetry capture implementation

This is the Phase 2 implementation handoff for the approved
[`telemetry-plan.md`](telemetry-plan.md) and
[`event-schemas.json`](event-schemas.json). The JSON catalogue is imported by
the backoffice and is the runtime property allowlist: unregistered event types,
missing required fields, wrong types, and extra keys are discarded before they
enter the queue. Rejected values are never written to the console.

## Capture pipeline

- `uis/backoffice/lib/telemetry.ts` is the one browser capture service. UI code
  emits through `track(eventType, properties)` only.
- The service generates `eventId`, UTC `timestamp`, `sessionId`, pseudonymous
  `userId`, `schemaVersion`, and `requestId`; callers provide none of them.
- Events flush as `{ "events": [...] }` every 10 seconds or at 20 queued events,
  whichever comes first. A failed batch gets three exponential-backoff retries.
- A hidden or closing tab uses `navigator.sendBeacon` for its pending batch.
- `POST /telemetry/events` validates the full envelope, logs only count and
  `event_type` labels, returns `{ "received": N }`, and intentionally stores
  nothing in this phase.

## Instrumentation map

| Event | Classification | Capture point |
| --- | --- | --- |
| `inbound_order_created` | Mandatory | `InventoryMovementForm`, after a committed receipt and refreshed stock |
| `outbound_order_created` | Mandatory | `InventoryMovementForm`, after a committed customer dispatch |
| `stock_threshold_triggered` | Mandatory | `InventoryMovementForm`, only on an at/above-to-below configured minimum transition |
| `direct_stock_edit_rejected` | Mandatory | FastAPI inventory invariant boundary, at the rejected `PATCH` attempt |
| `inventory_discrepancy_detected` | Mandatory | `InventoryAuditForm`, after a physical count differs from computed stock |
| `inventory_loss_recorded` | Identified | `InventoryMovementForm`, after a committed loss exit |
| `product_created` | Identified | `InventoryProductForm`, after a zero-stock SKU is committed |
| `inventory_validation_failed` | Identified | `InventoryMovementForm`, when an actionable field fails validation |
| `outbound_order_rejected` | Identified | `InventoryMovementForm`, on the client guard or API insufficient-stock response |
| `audit_history_viewed` | Identified | `InventoryOrders`, after the read-only feed loads |
| `login_succeeded` | Identified | `LoginForm` / `RegisterForm`, after authentication succeeds |
| `login_failed` | Identified | `LoginForm`, after a classified credential, account, rate, or network failure |
| `session_expired` | Identified | `AuthProvider`, on a rejected protected request |
| `authorization_denied` | Identified | Central `authFetch`, on HTTP 403 |
| `password_reset_requested` | Identified | `ForgotPasswordForm`, after the privacy-neutral request outcome |
| `page_viewed` | Identified | `TelemetryRuntime`, on backoffice route changes |
| `workflow_started` | Identified | Inventory movement and SKU forms, on first meaningful interaction |
| `workflow_completed` | Identified | Inventory movement and SKU forms, after successful commit |
| `workflow_abandoned` | Identified | `InventoryMovementForm`, when an unfinished flow unmounts |
| `api_latency_recorded` | Identified | Central `authFetch`, for errors, SLO breaches, and the approved success sample |
| `page_load_recorded` | Identified | `TelemetryRuntime`, from Next.js LCP Web Vital |
| `frontend_error_captured` | Identified | global listeners plus App Router route/root error boundaries |
| `api_error_returned` | Identified | Central `authFetch`, on every HTTP 4xx/5xx response |

## Privacy and operational rules

The browser never sends client display names, user names, email addresses,
passwords, receipt references, or tracking numbers. TinyDB user UUIDs are
HMAC-pseudonymised by FastAPI before reaching the browser. The inventory API
returns governed opaque client ids for the four CONTEXT seed clients; it does
not manufacture identifiers for unknown clients. Stock minimums are governed
per seed SKU and remain separate from the visual table status.

The physical-count endpoint is a comparison only. It returns an opaque audit
id and a signed variance but does not write stock; TrackFlow stock remains
derived exclusively from inbound minus outbound movements.

## Verification

Automated coverage includes envelope validation, safe logging, pseudonymous
identity stability, 20-event and 10-second flushes, allowlist rejection,
three-retry backoff, `sendBeacon`, inventory audit non-mutation, direct-edit
rejection, environment resolution, and governed inventory dimensions.

The reproducible live transcript is recorded in
[`capture-verification.txt`](capture-verification.txt): a real backoffice page
queued `page_viewed`, the browser posted the batch after 10 seconds, and the
local FastAPI stub responded HTTP 200 without logging properties.
