# TrackFlow telemetry storage implementation

This is the Phase 3 backend handoff for the approved
[`telemetry-plan.md`](telemetry-plan.md),
[`event-schemas.json`](event-schemas.json), and the existing browser capture
pipeline. The frontend remains unchanged.

## Storage contract

`models.TelemetryEventRecord` maps to the append-only Supabase/PostgreSQL
table `telemetry_events` with exactly eight columns: `id`, `timestamp`,
`service`, `event_type`, `level`, `value`, `message`, and `tags`.

- `id` is a UUID with database default `gen_random_uuid()`.
- `timestamp` is timezone-aware and indexed.
- `event_type` is indexed.
- `tags` is JSONB with a GIN index.
- `service` is constrained to `backoffice | api`; `level` is constrained to
  `info | warn | error`.
- There is no update or delete endpoint, repository helper, or model workflow.
  The checked-in idempotent migration revokes update, delete, and truncate
  privileges from Supabase's client roles.

The reproducible DDL is
[`services/api/migrations/20260923_create_telemetry_events.sql`](../../services/api/migrations/20260923_create_telemetry_events.sql).
Application startup also runs SQLModel metadata creation against the same
`DATABASE_URL`, keeping fresh environments and the ORM definition aligned.

## Partial batch acceptance

The endpoint accepts only the outer shape `{ "events": [...] }`. Its item type
is deliberately loose. Inside the route, every item is passed independently to
the unchanged `TelemetryEvent.model_validate(...)` model and then to the
approved event-specific catalogue validator.

Invalid envelopes still receive HTTP 422. Invalid events inside a valid
envelope increment `rejected`; their valid siblings are inserted and the
endpoint returns HTTP 200 with `{ "received", "stored", "rejected" }`.
Rejected payload contents are never logged.

## One insert per batch

After validation, rows are mapped in memory and submitted through one SQL
Core executemany `INSERT`, followed by one commit. A regression test listens to
SQLAlchemy's statement hook and proves that a heterogeneous three-event batch
emits exactly one `INSERT INTO telemetry_events` statement.

## Privacy-preserving tags

`tags` contains only properties allowed for the exact `event_type` in
`event-schemas.json`, plus the five correlation fields documented in the
storage mapping section of `telemetry-plan.md`. The service never copies raw
request bodies, error messages, URLs, credentials, email addresses, display
names, purchase-order references, or tracking numbers into storage.

## Verification

Automated tests cover:

- mixed valid/invalid batches and non-object list items;
- whole-envelope 422 boundaries;
- all envelope constraints from the unchanged Phase 2 model;
- event-specific required keys, types, enums, ranges, patterns, UUID formats,
  and unknown-property rejection;
- exact table columns and all three indexes, including PostgreSQL GIN;
- one bulk insert for heterogeneous valid events;
- `service`, `level`, `value`, and tags mapping;
- safe count/type-only logs and HMAC-pseudonymous identities.
