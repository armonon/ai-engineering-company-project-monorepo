# RFP workflow Part 1 — intake and routing

The backoffice `/rfp` page uploads a PDF to the existing FastAPI service. The
request validates and stores it under `data/raw/`, inserts one PostgreSQL ticket
with `analyzing`, schedules a background task, and returns `202` immediately.
The UI polls that same ticket until it becomes `intake_complete` or `discarded`.

## Dedicated graph

`data/pipelines/rfp_intake/` owns the graph; the HTTP router only triggers it and
persists its result. Nodes execute in this order:

1. `convert_pdf` — MarkItDown converts the PDF before any agent reads it. A
   documented `pdftotext` fallback supports local recovery.
2. `classify` — accepts formal and informal client requests, rejects inbound
   supplier/carrier pitches, and stops invalid documents.
3. `extract_metadata` — extracts client, country/currency, requested services,
   monthly volume, deadline, budget, applicable departments, and readability.
4. `orchestrate` — creates work only for TrackFlow's exact active departments.
5. `department_workers` — parallel workers receive shared metadata plus only
   their relevant extracts. Missing figures become `OPEN QUESTION`; no worker
   invents them.
6. `synthesize` — creates the Sales summary and Part 2 handoff containing
   `ticket_id`, metadata, and the scoped workstream/key-aspect structure.

The source of truth is PostgreSQL/Supabase: `rfp_tickets`, `rfp_metadata`, and
`rfp_department_sections`. Uploaded PDF/Markdown files are runtime artifacts,
not JSON-file persistence. A failed background job keeps the ticket available
with `processing_error` for retry instead of silently discarding it.

## TrackFlow routing contract

| Request | Classification | Departments | Currency |
| --- | --- | --- | --- |
| ModaViva formal RFP | accept | `warehouse`, `reverse` | EUR |
| Luna Cosmetics informal email | accept | `warehouse`, `lastmile` | USD |
| RapidShip inbound carrier pitch | discard | none | none |

Owners are fixed by the briefing: Ana Whitfield (`warehouse`), Carlos Vega
(`lastmile`), and Sofía Ramos (`reverse`).

## Verification

```bash
services/api/.venv/bin/pytest -q \
  tests/pipelines/test_rfp_intake.py services/api/tests/test_rfp.py
npm run test --workspace @trackflow/backoffice -- --runInBand
services/api/.venv/bin/python scripts/rfp_intake_smoke.py path/to/request.pdf
```
