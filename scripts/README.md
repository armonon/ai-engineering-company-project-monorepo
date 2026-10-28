# `scripts/`

Standalone scripts for TrackFlow runtime work and read-only coursework checks.

## `nightly_export.py` — independent nightly telemetry job

```bash
services/api/.venv/bin/python scripts/nightly_export.py
TARGET_DATE=2026-07-15 services/api/.venv/bin/python scripts/nightly_export.py
```

The script exports the selected UTC day from `telemetry_events` to the ignored
`data/raw/telemetry_YYYY-MM-DD.csv` audit file, then launches the existing
Milestone 6 pipeline as a subprocess. It records the full lifecycle in
`job_runs`, uses `processing` as its only cross-process lock, and skips a date
that is already `completed`.

Production uses the checked-in system crontab at
`infra/cron/trackflow-nightly-export.cron`: `0 2 * * *` in UTC. OS cron was
chosen because the job must remain operationally independent from FastAPI; a
framework scheduler in the API process would share its failure and restart
boundary. Ensure `/var/log/trackflow` exists and install the crontab with the
deployment configuration for the `trackflow` service account.

## `analyze.py` — Incident Report Analyser (Phase 1)

```bash
python scripts/analyze.py scripts/incidents-trackflow.csv
```

Reads the CSV, validates every row against the rules in
[`CONTEXT.md`](../CONTEXT.md), prints the summary, and offers to
export a CSV with one row per metric.

Uses the shared `incident_analyzer` package (under
[`../packages/incident_analyzer`](../packages/incident_analyzer)),
which is the same module the API imports — analysis and validation
logic is not duplicated.

Flags:
- `--out results.csv` — where to write the exported CSV
  (default `results.csv`).
- `--no-prompt` — skip the y/n export prompt (used by CI).

The bundled `incidents-trackflow.csv` is the 100-row sample from the
syllabus. Expected values are documented in `CONTEXT.md`
(§ Data Distribution).

## 4Geeks coursework scripts

Moved to [4geeks-coursework-agent](https://github.com/armonon/4geeks-coursework-agent) — they query the
4Geeks student API and belong with the agent that calls them, not with
TrackFlow's build tooling.
