# `data/pipelines` folder

This folder groups **all data pipelines in the monorepo** related to the company: ingestion, ETL/ELT, cleaning, transformation, and loading into analytical or production systems.

Each subfolder or file under `data/pipelines/` should represent **one pipeline or job set** (for example `sales-etl`, `telemetry-stream`, `customer-segmentation`) and include the required configuration (scripts, orchestration, connectors, schemas, etc.).

- **Main purpose**: consolidate in one place the data movement and transformation logic that powers the company’s applications and analytics.
- **Recommendation**: document pipelines as you add them—their goal, data sources and sinks, dependencies, and how to run them in development, testing, and production.

> _Spanish version: [README.es.md](./README.es.md)._

## Weekly Warehouse & Client Performance pipeline

[`pipeline.py`](./pipeline.py) implements TrackFlow's approved Milestone 6
business pipeline with Prefect 3. It reads only the four governed business
event types from `telemetry_events`, transforms them through the pure module in
`data/process/`, and idempotently publishes one row per warehouse, client, and
UTC ISO week to `reporting.weekly_warehouse_client_performance`.

The parent `weekly_warehouse_client_performance_flow` composes three explicit
subflows with typed inputs and outputs: extraction, transformation, and load.
The local evaluation snapshot is a fourth optional subflow invoked with
`return_state=True`, so its failure is visible without invalidating an already
committed business publication.

From the repository root, after `cd services/api && uv sync`:

```bash
services/api/.venv/bin/python data/pipelines/pipeline.py
services/api/.venv/bin/python data/pipelines/pipeline.py --week-start 2026-07-13
```

The command reads `DATABASE_URL` from the environment or the ignored
`services/api/.env`. It never accepts or prints credentials. The default window
is the most recently completed UTC ISO week. Runtime evaluation snapshots land
under the ignored `data/eval/pipeline-runs/` directory.

Pure transformation coverage lives in `tests/pipelines/test_pipeline.py` and
requires no database or network connection:

```bash
services/api/.venv/bin/python -m pytest tests/pipelines/test_pipeline.py -q
```
