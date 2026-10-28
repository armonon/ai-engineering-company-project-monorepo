# `data/raw` folder

This folder is intended for **raw data** related to the company: dumps, exports, sample files, event samples, or untransformed datasets.

- **Main purpose**: serve as a landing zone or reference for original data before pipelines process it.
- **Recommendation**: document each dataset’s origin, format, expected size, privacy/PII considerations, and how it is versioned (ideally avoiding sensitive data in the repository).

`scripts/nightly_export.py` writes UTC daily telemetry audit snapshots here as
`telemetry_YYYY-MM-DD.csv`. They are generated from the append-only
`telemetry_events` table, may contain pseudonymous operational identifiers, and
are therefore gitignored. The business pipeline continues to read PostgreSQL;
these CSV files are backup/recovery evidence, not pipeline input.

> _Spanish version: [README.es.md](./README.es.md)._
