# TrackFlow Telemetry Plan

Status: implementation-ready design

Schema catalogue: [`event-schemas.json`](./event-schemas.json)
Company source: [TrackFlow telemetry context](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/06-telemetry-data-pipelines/telemetry/CONTEXT-trackflow.md)

## 1. Scope and outcome

This plan answers the management RFI for TrackFlow's Los Angeles and Zaragoza
inventory programme. It specifies what the existing backoffice and FastAPI
service should capture; it does **not** add instrumentation or a new server.

The catalogue contains **23 events**:

- **5 mandatory events** copied exactly from the TrackFlow telemetry context;
- **18 identified opportunities** grounded in the current inventory,
  authentication, navigation, workflow, performance, frontend-error, and
  API-error surfaces;
- **6 categories** in total.

The five mandatory event identifiers are:

1. `inbound_order_created`
2. `outbound_order_created`
3. `stock_threshold_triggered`
4. `direct_stock_edit_rejected`
5. `inventory_discrepancy_detected`

### Domain mapping

The telemetry context calls the business entities `Product`, `InboundOrder`,
and `OutboundOrder`. The existing API implements those concepts as `SKU`,
`StockEntry`, and `StockExit`. Telemetry keeps the course-defined identifiers:

| Telemetry concept | Existing implementation | Telemetry field/value |
| --- | --- | --- |
| Product | `SKU` | `product_id` |
| InboundOrder | `StockEntry` | `inbound_order_created` |
| OutboundOrder (dispatch) | `StockExit(exit_type="dispatch")` | `outbound_order_created` |
| Confirmed warehouse loss | `StockExit(exit_type="loss")` | `inventory_loss_recorded` |
| Los Angeles | `warehouse="LA"` | `warehouse="los_angeles"` |
| Zaragoza | `warehouse="ZGZ"` | `warehouse="zaragoza"` |

The producer performs the warehouse mapping before emission. Consumers never
need to understand the API's abbreviations. Each SKU belongs to exactly one
`client_id`; an event must obtain that client from the stored SKU, never from a
caller-supplied override.

Country is a governed derived dimension rather than a repeated producer field:
`los_angeles -> US` and `zaragoza -> ES`. That fixed mapping lets Ana and
Thomas aggregate by country without allowing contradictory warehouse/country
pairs into raw events.

### Instrumentation prerequisites exposed by this plan

The current inventory API stores `client_name`, not a stable `client_id`, and
does not yet store a client-specific minimum-stock configuration. Those gaps do
not justify inventing telemetry values:

- Before inventory capture ships, create or connect to the authoritative B2B
  client registry and resolve an immutable opaque `client_id` from the stored
  SKU. Never hash `client_name` and call the result a business identifier.
- Add a governed per-client/per-SKU minimum-stock policy as the source of
  `threshold_quantity`. The backoffice's generic “low stock” presentation
  threshold is not a substitute for the mandatory client threshold metric.
- `inventory_discrepancy_detected` remains dormant until a physical-count or
  reconciliation process exists. Do not fabricate audit events from ordinary
  outbound losses.
- `direct_stock_edit_rejected` belongs at the API enforcement boundary. It
  measures a forbidden attempted write even though the supported backoffice
  intentionally exposes no direct-stock edit control.

## 2. Inventory-flow instrumentation map

This is the end-to-end path from protected access to a completed inbound or
outbound order. The same `sessionId` follows the browser session and the same
`requestId` follows a submission across browser and API events.

| Point | Flow stage | Instrumentation | Producer and success boundary |
| --- | --- | --- | --- |
| 1 | User opens a protected inventory route | `session_expired`, `page_viewed` | `AuthProvider` emits expiry only after the API returns a token-expiry 401; route view emits after auth succeeds. |
| 2 | Products page becomes usable | `page_load_recorded`, `api_latency_recorded` | Browser measures usable content; FastAPI middleware measures `GET /inventory/products`. |
| 3 | Operator begins a form | `workflow_started` | Backoffice emits on the first meaningful interaction, not merely on render. |
| 4 | Form rejects invalid input | `inventory_validation_failed` | Backoffice emits after a valid SKU is selected, using field/reason codes and never the raw value. |
| 5 | User attempts a forbidden stock mutation | `direct_stock_edit_rejected` | FastAPI emits one unsampled control event while rejecting the write; no database mutation occurs. |
| 6 | Backend rejects an outbound request | `outbound_order_rejected`, `api_error_returned` | Inventory router emits the business event before returning controlled HTTP 400; middleware emits the sanitised API result. |
| 7 | Inbound transaction commits | `inbound_order_created` | Transactional outbox emits only after `StockEntry` commit succeeds. |
| 8 | Dispatch or loss commits | `outbound_order_created` or `inventory_loss_recorded` | Transactional outbox selects one event from `exit_type`; retries reuse/deduplicate the same event id. |
| 9 | Committed movement crosses a minimum | `stock_threshold_triggered` | Backend compares warehouse-scoped stock before/after the movement and emits only on the threshold transition. |
| 10 | Operator finishes or leaves the flow | `workflow_completed`, `workflow_abandoned` | Success is emitted after API confirmation; abandonment is derived in batch from a start with no completion. |
| 11 | Operator reviews movement history | `audit_history_viewed` | Backoffice emits after `GET /inventory/orders` succeeds, including filters and count but no row contents. |
| 12 | Physical audit finds a variance | `inventory_discrepancy_detected` | Reconciliation process emits after comparing physical and computed warehouse stock. |

The mandatory direct-edit event represents a rejected attempt against the
derived-stock invariant. The current UI exposes no edit control, but the API
boundary must still reject and measure crafted or legacy requests.

## 3. Standard Event Envelope

Every raw and derived event uses the same envelope. Producers must reject an
event before transport if an envelope field is missing, the `event_type` is not
registered, a required property is missing, or a property is not allowlisted.

| Field | Type and validation | Meaning |
| --- | --- | --- |
| `eventId` | UUID string, required | Producer-generated idempotency key; consumers deduplicate on it. |
| `timestamp` | ISO 8601 UTC string ending in `Z`, required | Time the fact occurred, not ingestion time. |
| `sessionId` | Non-empty opaque string, required | Random browser/session identifier; never a cookie or bearer token. Backend-only work uses a new service session id. |
| `userId` | Non-empty string, required | `usr_` plus an HMAC of the TinyDB user UUID; use `anonymous` before authentication and `system` for scheduled processes. |
| `event_type` | `entity_action` lowercase snake case, required | Stable identifier registered in this catalogue. |
| `schemaVersion` | semantic version such as `1.0.0`, required | Version of the selected event contract. |
| `requestId` | Non-empty correlation id, required | Browser-generated for requests and propagated in `X-Request-ID`; service jobs generate one per run. |
| `properties` | Object, required | Event-specific allowlisted fields only; unknown keys are rejected. |

Example with deliberately fake opaque identifiers:

```json
{
  "eventId": "4c94ba70-4cbc-4b30-81a8-0f94bf730f87",
  "timestamp": "2026-09-01T19:45:12.482Z",
  "sessionId": "sess_6997c20d0fd94aa9",
  "userId": "usr_08b7bd14e1c0",
  "event_type": "inbound_order_created",
  "schemaVersion": "1.0.0",
  "requestId": "req_74f7282e456b4ce9",
  "properties": {
    "warehouse": "los_angeles",
    "client_id": "client_018",
    "product_id": "sku_204",
    "product_category": "electronics",
    "quantity": 40,
    "order_id": "entry_901",
    "stock_after": 108,
    "reference_present": true
  }
}
```

### Identity, correlation, ordering, and evolution

- The browser creates `requestId` before an API call. FastAPI returns it and
  attaches it to latency, error, and committed business events.
- Authenticated `userId` values are HMAC-SHA-256 pseudonyms. The HMAC key lives
  in the secret manager and rotates annually with a controlled overlap window.
  Login-failure `principal_hash` uses a separate key that rotates every 30 days.
- Delivery is at least once. `eventId` is the deduplication key. Business events
  use a transactional outbox so database rollback cannot create a false event.
- `timestamp` is event time in UTC. Ingestion also records server receive time
  outside the event envelope so pipelines can measure lateness and clock skew.
- Additive optional properties increment the minor `schemaVersion`; removals,
  type changes, or semantic changes increment the major version. Consumers must
  reject unknown major versions and ignore only documented optional omissions.
- Dynamic ids never appear in route properties: use `/inventory/products/{id}`
  rather than the raw path. Query strings and fragments are discarded.

## 4. Event opportunity catalogue and decision test

Each row deliberately completes the required sentence: **we capture the event
because we need to know the hypothesis, which allows us to make the stated
decision**. Events without a concrete decision were excluded.

| Event | Class / category | Trigger and golden-rule justification |
| --- | --- | --- |
| `inbound_order_created` | Mandatory / business inventory | Fires after a receipt commits. We capture it because we need to know incoming units by client, warehouse, country, and time, which allows Ana to plan capacity and staffing. |
| `outbound_order_created` | Mandatory / business inventory | Fires after a customer dispatch commits. We capture it because we need to know dispatched order volume and rate by client and warehouse, which allows Ana to find bottlenecks before delivery SLA is affected. |
| `stock_threshold_triggered` | Mandatory / business inventory | Fires when warehouse-scoped stock crosses from above to at/below the client's minimum. We capture it because we need to know how often each client approaches a SKU stockout, which allows Miguel to alert the client and commercial team before fulfilment stops. |
| `direct_stock_edit_rejected` | Mandatory / business inventory | Fires when the API rejects stock mutation outside an order. We capture it because we need to know whether staff try to bypass traceability and where, which allows operations to change training or permissions. |
| `inventory_discrepancy_detected` | Mandatory / business inventory | Fires when an audit's physical count differs from computed stock. We capture it because we need to know discrepancy frequency and magnitude by SKU and warehouse, which allows Ana to prioritise audits and root-cause work. |
| `inventory_loss_recorded` | Opportunity / business inventory | Fires after a loss `StockExit` commits. We capture it because we need to know which warehouses, clients, and SKUs lose the most units, which allows operations to target handling controls without misclassifying losses as customer dispatches. |
| `product_created` | Opportunity / business inventory | Fires after a new SKU commits with zero stock. We capture it because we need to know catalogue growth by client/category/warehouse, which allows onboarding and storage capacity to be planned. |
| `inventory_validation_failed` | Opportunity / business inventory | Fires after a valid SKU is selected but the form rejects a controlled field rule. We capture it because we need to know which product/form rules confuse operators, which allows product to simplify forms or focus training. |
| `outbound_order_rejected` | Opportunity / business inventory | Fires when a known-SKU outbound request fails a business rule. We capture it because we need to know how often work is blocked by insufficient stock or dispatch validation, which allows shift leads to correct stock and process issues quickly. |
| `audit_history_viewed` | Opportunity / navigation workflow | Fires after movement history loads. We capture it because we need to know whether operators use the audit trail and with which filters, which allows product to prioritise audit and search improvements. |
| `login_succeeded` | Opportunity / authentication security | Fires when a valid session is created. We capture it because we need to know active backoffice adoption by role and time, which allows managers to schedule support and identify unused access. |
| `login_failed` | Opportunity / authentication security | Fires on a non-enumerating credential failure. We capture it because we need to know whether failures form an abuse burst or ordinary friction, which allows security to rate-limit and investigate without exposing account existence. |
| `session_expired` | Opportunity / authentication security | Fires once when an expired/revoked session is rejected. We capture it because we need to know whether expiry interrupts active workflows, which allows product and security to tune session duration. |
| `authorization_denied` | Opportunity / authentication security | Fires when role or ownership policy denies an authenticated request. We capture it because we need to know where permissions conflict with real work or indicate misuse, which allows administrators to correct roles or investigate. |
| `password_reset_requested` | Opportunity / authentication security | Fires when reset is accepted or rate-limited. We capture it because we need to know reset demand and abuse bursts, which allows support to improve recovery while security protects targeted accounts. |
| `page_viewed` | Opportunity / navigation workflow | Fires after an authenticated route transition. We capture it because we need to know which sections are used and from where, which allows product to reorganise navigation around operator behaviour. |
| `workflow_started` | Opportunity / navigation workflow | Fires on the first meaningful interaction in a defined flow. We capture it because we need a trustworthy funnel denominator, which allows product to compare starts with completion and abandonment. |
| `workflow_completed` | Opportunity / navigation workflow | Fires after the intended API-confirmed outcome. We capture it because we need to know successful conversion and time-to-task, which allows operations to compare workflows and training outcomes. |
| `workflow_abandoned` | Opportunity / navigation workflow | Is derived when a started flow has no completion by its watermark or ends on navigation/expiry. We capture it because we need to know where operators leave unfinished work, which allows product to remove the highest-impact friction. |
| `api_latency_recorded` | Opportunity / performance | Fires from FastAPI middleware for sampled healthy requests and every slow/error request. We capture it because we need to know endpoint latency percentiles and SLO breaches, which allows engineering to fix bottlenecks before warehouse work slows. |
| `page_load_recorded` | Opportunity / performance | Fires when a route becomes usable. We capture it because we need to know which views are slow by route and coarse device class, which allows frontend work to target the slowest operational surfaces. |
| `frontend_error_captured` | Opportunity / frontend errors | Fires from a client error boundary with a scrubbed fingerprint. We capture it because we need to know which releases and components break workflows, which allows engineering to triage and roll back quickly. |
| `api_error_returned` | Opportunity / API errors | Fires for controlled 4xx/5xx responses. We capture it because we need to know which endpoints and stable error codes block work, which allows engineering to distinguish user validation friction from service failure. |

## 5. Per-event property allowlists

The following tables are the Markdown schema contract. A property is allowed
only if it appears in its event row. `R` means required and `O` means optional.
The JSON catalogue repeats the name, type, required flag, validation constraints,
and description for machine validation. Every inventory event includes the
context minimum: `warehouse`, `client_id`, `product_id`, `product_category`, and
`quantity`. The privacy column assesses event-specific properties; the envelope's
pseudonymous `userId` is sensitive and access-controlled for every event.

### Business inventory

| Event | Required properties: type — meaning | Optional properties: type — meaning | Sensitive/PII |
| --- | --- | --- | --- |
| `inbound_order_created` | `warehouse:string(enum)` — normalised receiving warehouse; `client_id:string` — opaque owner; `product_id:string` — opaque SKU; `product_category:string(enum)` — category; `quantity:integer>=1` — received units; `order_id:string` — opaque entry id | `stock_after:integer>=0` — computed post-commit stock; `reference_present:boolean` — reference existence only | Commercially sensitive internal IDs and quantities; never emit reference text or recipient data. |
| `outbound_order_created` | `warehouse:string(enum)` — dispatch warehouse; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer>=1` — dispatched units; `order_id:string` — opaque exit id; `exit_type:string="dispatch"` — excludes losses | `stock_after:integer>=0`; `tracking_present:boolean` — never the number | Commercially sensitive internal IDs and quantities; tracking and recipient data are excluded. |
| `stock_threshold_triggered` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer>=0` — current stock; `threshold_quantity:integer>=0`; `previous_quantity:integer>=0`; `trigger_source:string(enum)` — order, loss, or reconciliation | None | Commercially sensitive client/SKU stock; client contacts are excluded. |
| `direct_stock_edit_rejected` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer` — attempted value/delta; `attempted_operation:string(enum)` — set/increment/decrement; `endpoint_template:string(enum)`; `reason_code:string="stock_is_derived"` | None | Commercially sensitive client/SKU attempt; raw bodies and credentials are excluded. |
| `inventory_discrepancy_detected` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer>=1` — absolute variance; `audit_id:string`; `system_quantity:integer>=0`; `physical_quantity:integer>=0`; `variance_quantity:integer`; `detection_method:string(enum)` | None | Commercially sensitive audit and stock variance; notes and photos are excluded. |
| `inventory_loss_recorded` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer>=1` — units lost; `order_id:string`; `exit_type:string="loss"` | `stock_after:integer>=0` | Commercially sensitive internal IDs and loss quantities; notes/photos are excluded. |
| `product_created` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer=0` — proves stock was not set directly | None | Commercially sensitive client/SKU identifiers; product names are excluded. |
| `inventory_validation_failed` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer` — attempted units or zero; `form_type:string(enum)`; `field_name:string(enum)`; `reason_code:string(enum)`; `occurrence_count:integer>=1` | None | Commercially sensitive IDs/quantity; rejected raw values and error text are excluded. |
| `outbound_order_rejected` | `warehouse:string(enum)`; `client_id:string`; `product_id:string`; `product_category:string(enum)`; `quantity:integer>=1`; `available_quantity:integer>=0`; `exit_type:string(enum)`; `reason_code:string(enum)` | None | Commercially sensitive IDs/quantities; tracking values and response bodies are excluded. |

Warehouse enum is exactly `los_angeles | zaragoza`; category enum is exactly
`fashion | electronics | cosmetics`.

### Authentication and security

| Event | Required properties: type — meaning | Optional properties: type — meaning | Sensitive/PII |
| --- | --- | --- | --- |
| `login_succeeded` | `auth_method:string="password"`; `role:string(enum)`; `session_age_seconds:integer=0` | None | Yes: user linkage. HMAC-pseudonymise `userId`; never send email/token/password/IP/user-agent. |
| `login_failed` | `auth_method:string="password"`; `reason_code:string(enum)` — non-enumerating result; `attempt_number:integer>=1` — server rate-limit window count | `principal_hash:string(pattern)` — rotating HMAC of normalised email | Yes. Raw identity and credentials are prohibited. |
| `session_expired` | `session_age_seconds:integer>=0`; `expiry_reason:string(enum)`; `route_template:string` — sanitised template | None | Yes: user linkage. Never emit token/cookie/raw URL. |
| `authorization_denied` | `endpoint_template:string`; `method:string(enum)`; `required_role:string(enum)`; `actual_role:string(enum)`; `reason_code:string(enum)` | None | Yes: user linkage. Use pseudonymous `userId`; exclude resource data. |
| `password_reset_requested` | `delivery_channel:string="email"`; `outcome:string(enum)` — accepted/rate-limited | `principal_hash:string(pattern)` — rotating HMAC | Yes. Email and reset token are prohibited. |

### Navigation and workflow

| Event | Required properties: type — meaning | Optional properties: type — meaning | Sensitive/PII |
| --- | --- | --- | --- |
| `audit_history_viewed` | `warehouse_filter:string(enum)`; `movement_filter:string(enum)`; `result_count:integer>=0`; `load_duration_ms:integer>=0` | None | No. Displayed movement rows are excluded. |
| `page_viewed` | `route_template:string`; `section:string(enum)`; `viewport_class:string(enum)` | `previous_section:string(enum)` | No. Raw URL, ids, queries, referrer, and browser fingerprint are excluded. |
| `workflow_started` | `workflow_name:string(enum)`; `flow_instance_id:UUID`; `entry_point:string(enum)` | None | No. Form values are excluded. |
| `workflow_completed` | `workflow_name:string(enum)`; `flow_instance_id:UUID`; `duration_ms:integer>=0`; `step_count:integer>=1`; `outcome:string="success"` | None | No. Submitted values are excluded. |
| `workflow_abandoned` | `workflow_name:string(enum)`; `flow_instance_id:UUID`; `duration_ms:integer>=0`; `last_step:string(enum)`; `abandonment_reason:string(enum)` | None | No. Typed but unsubmitted values are excluded. |

### Performance and errors

| Event | Required properties: type — meaning | Optional properties: type — meaning | Sensitive/PII |
| --- | --- | --- | --- |
| `api_latency_recorded` | `service:string="trackflow_api"`; `endpoint_template:string`; `method:string(enum)`; `status_class:string(enum)`; `duration_ms:integer>=0`; `slo_exceeded:boolean` | None | No. Paths, headers, bodies, IPs, queries, and user agents are excluded. |
| `page_load_recorded` | `route_template:string`; `duration_ms:integer>=0`; `navigation_type:string(enum)`; `viewport_class:string(enum)`; `threshold_exceeded:boolean` | None | No. Full URL and fingerprinting attributes are excluded. |
| `frontend_error_captured` | `error_code:string(pattern)`; `error_fingerprint:string(pattern)`; `component:string`; `route_template:string`; `release:string`; `handled:boolean`; `occurrence_count:integer>=1` | None | Potentially. Only scrubbed codes/fingerprints are allowed; raw messages, stack values, DOM, form data, URLs, and tokens are prohibited. |
| `api_error_returned` | `service:string="trackflow_api"`; `endpoint_template:string`; `method:string(enum)`; `status_code:integer(400..599)`; `error_code:string(pattern)`; `duration_ms:integer>=0`; `retryable:boolean` | None | No. Exception text, traceback, request/response data, headers, and database URLs are prohibited. |

### Custom JSON validation algorithm

`event-schemas.json` uses the documented custom format
`trackflow.telemetry.catalogue/1.0.0`. A producer validator must:

1. reject envelope keys not declared in `envelope.fields` because
   `envelope.additionalProperties` is false;
2. require every name in `envelope.required` and validate its type, format,
   pattern, and length rules;
3. look up `event_type` as an exact key in `events`, require the entry's own
   `event_type` to match that key, and require the envelope `schemaVersion` to
   equal the version declared by the event entry;
4. build the event's allowlist from `events[event_type].properties.fields`;
5. reject unknown property keys because the event's `additionalProperties` is
   false; and
6. require every property whose field definition has `required: true`, then
   enforce type, enum, format, pattern, minimum, maximum, and length rules.

Failure to validate is a producer defect. Invalid telemetry is logged as a
counted internal metric without copying the rejected event payload into logs.

## 6. Delivery strategy

### Event-by-event mode and urgency

| Mode | Events | Business/operational reason |
| --- | --- | --- |
| Stream | `inbound_order_created`, `outbound_order_created`, `inventory_loss_recorded` | Stock and shift throughput change immediately; operations need seconds-level freshness. |
| Stream | `stock_threshold_triggered`, `inventory_discrepancy_detected` | Stockout and contractual discrepancy risk require prompt alerts. |
| Stream | `direct_stock_edit_rejected`, `outbound_order_rejected` | Control bypass or repeated blocked dispatches can require same-shift intervention. |
| Stream | `login_failed`, `authorization_denied`, `password_reset_requested` | Security bursts and permission misuse require near-real-time detection. |
| Stream | `api_latency_recorded`, `frontend_error_captured`, `api_error_returned` | SLO/error spikes can block live warehouse work and need fast triage. |
| Batch daily | `product_created`, `inventory_validation_failed`, `login_succeeded`, `session_expired`, `audit_history_viewed`, `page_viewed`, `workflow_started`, `workflow_completed`, `page_load_recorded` | Catalogue growth, adoption, UX, and healthy performance feed trend and prioritisation decisions rather than immediate response. |
| Batch hourly, derived | `workflow_abandoned` | Abandonment requires event-time joins and a lateness watermark; immediate emission would misclassify slow but successful work. |

Stream means available to alerting/operations within 60 seconds. Batch events
are buffered to object storage and processed daily at 02:00 UTC unless the
table says hourly. Batch/stream describes decision latency, not producer
technology: all producers still validate the same envelope.

### Throttle, debounce, and sampling

- Mandatory inventory events, committed losses, business rejections, security
  denials, password resets, and all 5xx errors are never sampled.
- `stock_threshold_triggered` emits on a state transition, not every movement
  while stock remains low. It re-arms only after stock rises above the minimum.
- `inventory_validation_failed` groups identical session/form/field/reason/SKU
  failures for 10 seconds and emits `occurrence_count`.
- `page_viewed` emits once per completed transition and suppresses the same
  route within five seconds. It never emits scroll, mouse-move, or keystroke
  events.
- `workflow_started` and `workflow_completed` emit at most once per
  `flow_instance_id`. Abandonment uses a 30-minute form watermark and a
  10-minute freight-quote watermark.
- `api_latency_recorded` and `page_load_recorded` retain 100% of errors/slow
  samples and a deterministic 10% sample of healthy traffic keyed by
  `requestId`; deterministic sampling keeps correlated frontend/backend pairs.
- `frontend_error_captured` groups the same fingerprint, route, release, and
  session for 60 seconds and increments `occurrence_count`.

### Retention and access

| Data | Raw retention | Aggregate retention | Access |
| --- | --- | --- | --- |
| Mandatory inventory and committed loss events | 13 months | 36 months | Warehouse operations, finance analytics, authorised engineering |
| Auth/security events | 90 days | 13 months | Security and authorised platform engineering |
| Navigation/workflow events | 90 days | 13 months | Product analytics and authorised engineering |
| Performance/error events | 30 days | 13 months | Engineering and SRE |

Data is encrypted in transit and at rest. Warehouse/client dashboards receive
aggregates and tenant-scoped results; no client can query another client's raw
events. Deletion jobs enforce retention by category.

## 7. Privacy, sensitive-data handling, and exclusions

### Never capture

- end-consumer name, address, phone, email, precise location, or package details;
- carrier identity or tracking number in inventory telemetry;
- passwords, reset tokens, bearer tokens, cookies, API keys, database URLs, or
  request/response bodies;
- raw B2B contact emails; use an approved rotating HMAC only when abuse
  correlation has a documented need;
- raw exception messages, stack values, SQL, DOM snapshots, field values, or
  unsubmitted form contents;
- full URLs, dynamic path ids, query strings, fragments, referrer URLs, IP
  addresses, user agents, or high-entropy browser/device attributes;
- mouse movement, keystrokes, clipboard contents, screenshots, or session replay.

`userId`, `principal_hash`, `client_id`, `product_id`, `order_id`, and
`audit_id` are sensitive internal identifiers even when pseudonymous. Access is
role-limited, and analysts receive only the minimum fields needed for their
question. HMAC pseudonyms are not reversible and their keys never enter the
event system.

### Considered and discarded events

| Candidate | Why it is excluded |
| --- | --- |
| `form_field_changed` / keystroke capture | High volume, exposes unsubmitted values, and adds no decision beyond validation/funnel events. |
| `mouse_moved`, click coordinates, heatmaps | Cost and fingerprinting/privacy risk exceed the navigation question's value. |
| Raw `request_received` for every API call | Duplicates `api_latency_recorded`; healthy traffic is sampled while all failures are retained. |
| `tracking_number_viewed` | Tracking and end-consumer delivery belong to the separate last-mile domain, not inventory telemetry. |
| Raw purchase-order/reference value | A boolean proves operational completeness without leaking client text. |
| `recipient_delivery_*` events | Explicitly outside this inventory plan and likely to contain end-consumer PII. |
| Raw error/stack/request payload capture | Unbounded secrets/PII risk; stable codes and scrubbed fingerprints answer the triage question. |
| Continuous stock snapshots | Expensive and redundant because current stock is derived from orders; emit committed movements and threshold transitions instead. |
| `logout_clicked` | Does not drive a current business decision; session expiry and workflow abandonment cover the actionable questions. |
| Individual report export tracking | No export surface exists in the current backoffice, so instrumentation would be speculative. |

### Risks and mitigations

| Risk | Consequence | Mitigation |
| --- | --- | --- |
| Client and server both claim the same business outcome | Double-counted orders | Backend outbox is authoritative for committed business events; browser emits workflow lifecycle only. |
| Event emitted before transaction commit | Telemetry reports stock that never changed | Transactional outbox writes with the business transaction and publishes after commit. |
| LA/ZGZ and long warehouse names mix | Broken aggregation | Producer mapping is fixed: `LA -> los_angeles`, `ZGZ -> zaragoza`; schema enum rejects alternatives. |
| High-cardinality URLs/errors create cost explosions | Slow, expensive analytics | Route templates, stable error codes, allowlists, sampling, and fingerprints. |
| Late workflow completion creates false abandonment | Inflated drop-off | Event-time watermark plus suppression/retraction when completion arrives within allowed lateness. |
| Replayed messages inflate metrics | Duplicate counts | At-least-once delivery with consumer deduplication on `eventId`. |
| HMAC key rotation breaks longitudinal analysis | Fragmented user trends | Version keys internally and use a controlled overlap; never expose the key version as a public analytic dimension. |
| Analytics access crosses client boundaries | Confidentiality breach | Apply the same tenant/client isolation as the API and publish only scoped aggregates. |
| Schema producer and documentation drift | Invalid or misleading events | CI parses JSON, compares event ids/counts with this plan, and validates representative valid/invalid fixtures. |

## 8. Instrumentation handoff

Implementation should proceed in this order:

1. Build a shared validator/emitter from `event-schemas.json`; fail closed on
   unknown fields and add deterministic unit fixtures.
2. Add request-id middleware and propagate `X-Request-ID` through the existing
   backoffice API client.
3. Add the inventory transactional outbox and the five mandatory events first.
4. Add security and API middleware events server-side.
5. Add browser navigation/workflow/performance/error producers without raw form
   or URL data.
6. Implement hourly abandonment derivation and daily aggregates.
7. Verify both warehouse mappings, all three categories, at least two clients,
   15–20 inbound orders, 15–20 outbound orders, two threshold transitions, and
   one discrepancy in non-production seed data.

Definition of done for instrumentation is not “an event was logged.” A fixture
must prove its envelope and allowlist validate, a forbidden property must fail,
the business transaction and event must agree, duplicate `eventId` values must
not double-count, and the resulting aggregate must answer the documented
decision question.
