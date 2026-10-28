# TrackFlow nightly job lifecycle service

This package owns the `job_runs` control table for Ticket DEV-53. It is a
small SQLAlchemy service used by `scripts/nightly_export.py`; it does not import
FastAPI and never runs on the API server's request thread.

The lifecycle is `pending → processing → completed | failed`. The
`processing` status is also the distributed lock: a partial unique database
index permits only one processing row for `nightly_export`. The unique
`(job_name, target_date)` key makes a completed UTC day idempotent. This is
separate from `reporting.pipeline_runs`, which records the internal ETL phases.

The matching PostgreSQL migration is
`services/api/migrations/20261028_create_job_runs.sql`. Runtime schema creation
keeps local SQLite demonstrations and tests reproducible.
