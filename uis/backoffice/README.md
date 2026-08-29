# TrackFlow Backoffice

The protected internal application for TrackFlow operations. It combines the
coursework features into one authenticated UI instead of sending an assessor
to several disconnected demos.

## Current modules

- Freight quote calculator
- Incident manager and incident analysis
- Inventory products, receipts, dispatches, losses, and movement history
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
