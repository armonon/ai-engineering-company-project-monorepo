# `services/reporting`

Authenticated HTTP boundary for TrackFlow's Weekly Warehouse & Client
Performance pipeline. This is deliberately separate from
`services/telemetry/`: technical telemetry reporting remains unchanged.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/reporting/pipeline-runs/latest` | Latest durable run metadata and status |
| `POST` | `/reporting/pipeline-runs` | Manager/admin trigger for a completed UTC ISO week |
| `GET` | `/reporting/weekly-warehouse-client-performance` | KPI rows for a Monday `week_start`, or the latest published week |

The endpoint module imports the flow, runner, and read-only query adapter from
`data/pipelines/`; it never duplicates transformation logic. All three routes
require the existing bearer-token authentication. The manual trigger is more
restricted because it starts operational work across clients.
