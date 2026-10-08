# Telemetry report — rubric and submission review

Source: [official assignment](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-telemetry-report/README.md)
and [TrackFlow context](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/06-telemetry-data-pipelines/telemetry/CONTEXT-trackflow.md),
read completely on 2026-10-07. This is the next company lesson after storage.

**Not yet submission-ready.** Depends on draft storage PR #29 and needs fresh
Supabase evidence: at least 20 real captured rows, technical and business types,
and an actual report response. Historical 34-row verification is not a fresh
claim. Report development and local verification can proceed independently.

## Exact rubric mapping

| Rubric | Implementation / verification |
| --- | --- |
| Required path and ≥3 independent metrics | `services/telemetry/analysis.py`: `events_per_day`, `error_rate_by_day`, `latency_by_endpoint`, `auth_failure_rate` |
| SQL event-type and half-open UTC time predicates | `analysis.py::_load`; `test_all_metric_queries_filter_timestamp_and_types_in_sql`, real database boundary cases in `services/api/tests/test_telemetry_report.py` |
| Refine dimensions then convert timestamp before grouping | Each function refines its population, calls `_dates` (`pd.to_datetime(..., utc=True)`), then groups |
| No metric loops; Pandas aggregates | `groupby`, `agg`, `count`, `sum`, `mean`, vectorised ratio division |
| JSON-serialisable lists of dictionaries | Each metric returns `reset_index().to_dict(orient="records")`; empty/populated endpoint tests |
| Side-effect-free, repeatable functions | Analysis accepts explicit connection/period; no clock/cache/writes; repeatability test |
| GET endpoint with optional ISO bounds and seven-day default | `services/api/routers/telemetry_report.py::report`, `_parse_date`; invalid/offset/default-window tests |
| `{period:{from,to},metrics:{...}}` | `report`; exact empty-response and populated metric tests |
| 60-second in-memory cache | `telemetry_report.py`: monotonic TTL, stable default keys, bounded 32 entries, engine isolation, cache hit/expiry tests |
| Technical/operational only; meaningful grouping | Counts by day/type, error-event share by day/service, API latency by day/endpoint, login-failure share by day; no revenue/conversion/stock metrics |
| Additional authentication metric | Included using actual `login_failed`/`login_succeeded` catalogue names; both selected in one SQL query |
| Additional visual dashboard | Not included; optional and not necessary for API deliverable |
| Real data and sample response in PR | Pending real Supabase access; local evidence explicitly labelled separately |

## Dependency and branch boundary

`codex/telemetry-technical-report` starts from accepted main and fast-forwards
through the verified storage head `cfc11a6` because reporting requires that
schema. PR targets main as requested; until #29 lands, its diff includes the
storage prerequisite. Review lesson-specific changes against `cfc11a6`. Do not
merge this PR first or mark it ready while prerequisite/evidence gates remain.
No new repository, canonical context changes, ingestion rewrites, frontend
changes, or secret files are needed.

## Teacher demonstration

1. Generate or confirm ≥20 real Supabase events, including technical/business.
2. Log in to the existing API and request an explicit report period covering
   those events. Show four metrics and explain their grouping/denominators.
3. Repeat the same period inside 60 seconds and demonstrate no new metric SQL
   reads; after expiry, show recalculation. Defaults retain the cached period.
4. Show inclusive start/exclusive end SQL, Pandas UTC conversion, and the
   independent analysis functions. Demonstrate 422 for an invalid period and
   401 without authentication.
5. Submit the PR titled `feat: telemetry report endpoint` once dependent work,
   current CI, independent review and live evidence are complete.

## Verified checks (2026-10-07)

- Fresh npm installation, workspace bootstrap, TypeScript checking and all
  production builds passed;96 JS/TS tests and381 API tests passed (19 report).
- UI lint, repository-wide Ruff, new Python-file formatting and production
  npm audit passed (zero vulnerabilities). Only build-generated tsconfig
  rewrites were restored; report lesson has no frontend diff.
- Independent OpenAI/Sol review cleared the implementation after fixing UTC
  conversion overflow at datetime bounds; all19 report tests independently pass.
- Real local Chromium/API runs generated actual login/inbound/outbound telemetry
  into isolated SQLite, then queried the authenticated report, repeated cached
  response and verified401/422. This is **not Supabase verification**. A sample
  is included in the PR body, explicitly labelled local.
- Actual Docker execution unavailable on this host. Docker source/package
  wiring was independently reviewed; Linux install/build gates run in CI.
