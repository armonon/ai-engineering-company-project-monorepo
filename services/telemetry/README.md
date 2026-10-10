# TrackFlow technical telemetry analysis

`analysis.py` is an installable, read-only Python package (`trackflow-telemetry`)
used by the existing FastAPI service, not another API or repository. Install
through `uv sync --project services/api --group dev --locked`. Docker/pip uses
the local editable entry in `services/requirements.txt`; the image includes
this package and the existing approved catalogue.

Four vectorised Pandas functions consume a SQLAlchemy connection and explicit
UTC `[start_date, end_date)` bounds. SQL filters both dates and event types.
The API supplies the approved catalogue for event-volume/error-share metrics;
latency and login functions select their exact relevant types in SQL.

- `events_per_day`: event count per UTC day and type, not inventory units.
- `error_rate_by_day`: error-level events / all catalogue events, per day/service.
  This is an **event share**, not an HTTP-request error probability. Failure
  login events have warning severity and are measured separately below.
- `latency_by_endpoint`: mean `api_latency_recorded.value` in milliseconds by
  UTC day and endpoint template; missing dimensions, missing/nonfinite/negative
  durations are excluded. Every observed endpoint is retained, not a selected
  single endpoint.
- `auth_failure_rate`: `login_failed / (login_failed + login_succeeded)` daily.
  These are the approved TrackFlow names; generic assignment aliases starting
  with `user_` do not exist in this company's capture catalogue.

No loops calculate metrics. No business metrics, writes, implicit clock,
credential access or HTTP code live in the analysis layer. Empty populations
return empty lists; missing days are not falsely represented as measured zeros.
Dates are UTC strings and rates are fractions between zero and one.

## API

Authenticated `GET /telemetry/report?start_date=...&end_date=...` accepts ISO
8601 dates/datetimes. Naive/date-only inputs mean UTC; explicit offsets are
normalised to UTC. End is exclusive. With neither bound supplied, the period
is the last seven days; with only end supplied, start is seven days before it;
with only start supplied, end is current UTC time. Invalid/reversed windows
return 422. The existing bearer login protects this internal aggregate report;
no individual user/client identity or raw tags are returned.

A monotonic 60-second cache holds at most 32 combinations per worker, keyed by
SQLAlchemy engine and normalised requested bounds. Omitted bounds have stable
keys: repeated default requests return the original resolved period until TTL
expiry (rather than recomputing a different `now` and missing every time).
Authentication runs even on cache hits. A lock coalesces concurrent misses;
failed calculations are not cached. Multiple workers have independent caches;
this is intentionally not Redis or a durable report store.

## Verification and limitations

Run `services/api/.venv/bin/python -m pytest services/api/tests/test_telemetry_report.py`.
Tests exercise real SQL and Pandas, half-open boundaries, query predicates,
ratio denominators, all endpoint dimensions, invalid values, empty data,
UTC-equivalent windows, repeatability, authentication and bounded/expiring cache.

This lesson depends on storage PR #29. Its required Supabase evidence is still
pending trusted login; local SQLite evidence must never be called a live
Supabase check. No new dashboard is included (optional activity omitted);
the authentication metric is included. See `docs/telemetry/report-submission-review.md`.
