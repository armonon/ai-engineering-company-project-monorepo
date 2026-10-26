# TrackFlow Backoffice

The protected internal application for TrackFlow operations. It combines the
coursework features into one authenticated UI instead of sending an assessor
to several disconnected demos.

## Inventory API configuration

For direct local development, copy `.env.example` to `.env.local` and keep
the file untracked:

```bash
cp .env.example .env.local
```

`NEXT_PUBLIC_INVENTORY_API_URL` points the authenticated backoffice at the
FastAPI service. Docker Compose leaves that override blank and uses the
same-origin `/trackflow-api` proxy, which reaches the backend container by
its `backend` service name.

The four inventory views use the assignment paths:

- `/backoffice/inventory/products`
- `/backoffice/inventory/orders/inbound`
- `/backoffice/inventory/orders/outbound`
- `/backoffice/inventory/orders`

## Telemetry capture

Set `NEXT_PUBLIC_TELEMETRY_ENDPOINT` in the untracked `.env.local` file. For
native development it is normally:

```text
NEXT_PUBLIC_TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events
```

All browser capture is centralised in `lib/telemetry.ts`. It validates event
properties against `docs/telemetry/event-schemas.json`, adds the standard
envelope, batches at 20 events or 10 seconds, retries a failed batch three times
with exponential backoff, and flushes pending events with `sendBeacon` when the
tab is hidden. The shared runtime captures navigation, LCP, and uncaught errors;
domain components add business events only at their confirmed decision points.

Additional governed inventory views support the approved event catalogue:

- `/backoffice/inventory/products/new` registers a zero-stock SKU.
- `/backoffice/inventory/audit` compares physical and computed stock without
  mutating it.

See [`../../docs/telemetry/capture-implementation.md`](../../docs/telemetry/capture-implementation.md)
for the complete event-to-component map and privacy contract.



## Current modules

- Freight quote calculator
- Incident manager and incident analysis
- Inventory products, receipts, dispatches, losses, and movement history
- Weekly Warehouse & Client Performance reporting under `/reporting`
- Talent Pipeline Tracker under `/talent`
- Supplier directory
- Profile, password recovery, and session management

The Talent Pipeline routes preserve the Milestone 3 workflows: candidate
search/filtering, registration, detail/edit views, status and stage updates,
and internal notes. The original `uis/talent-pipeline-tracker` workspace stays
in Git history and on the stable `milestone-3-talent-pipeline` branch as the
submission snapshot; the backoffice route is the cumulative company demo.

## Run locally

From the repository root:

```bash
npm install
npm run bootstrap
npm run dev --workspace @trackflow/backoffice
```

Open <http://localhost:3100>. With Docker Compose, the backoffice is available
at <http://localhost:3001>.

All routes except authentication and password recovery require a TrackFlow
account. Create one through `/register` or use an existing local account.

The reporting dashboard consumes the authenticated
`GET /reporting/weekly-warehouse-client-performance` endpoint. It shows the
completed UTC reporting period and all five approved TrackFlow KPIs, both as
stakeholder summary cards and by warehouse/client grain. It never queries the
telemetry storage table directly.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `/trackflow-api` | TrackFlow FastAPI base path |
| `TRACKFLOW_API_INTERNAL_URL` | `http://127.0.0.1:8000` | Server-side rewrite destination |
| `NEXT_PUBLIC_TALENT_API_URL` | `/talent-api` | Browser-facing Talent Tracker base path |
| `TALENT_API_INTERNAL_URL` | `https://playground.4geeks.com/tracker/api/v1` | Server-side Talent Tracker rewrite destination |

The candidate service has its own variables so it cannot accidentally send
candidate traffic to the authenticated inventory/auth API. The same-origin
rewrite also avoids depending on cross-origin browser policy.

## Verify

```bash
npm run typecheck --workspace @trackflow/backoffice
npm test --workspace @trackflow/backoffice -- --runInBand
npm run lint --workspace @trackflow/backoffice
npm run build --workspace @trackflow/backoffice
```
