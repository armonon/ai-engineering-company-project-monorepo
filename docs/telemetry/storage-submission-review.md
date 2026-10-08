# Telemetry storage: submission review

Reviewed on 2026-10-07 against the official
[storage assignment](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/projects/ai-eng-telemetry-storage/README.md)
and [TrackFlow telemetry context](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/06-telemetry-data-pipelines/telemetry/CONTEXT-trackflow.md).
The assignment's `CONTEXT-company.md` means this company-specific context;
the monorepo's shared vocabulary remains governed by `CONTEXT.md` and its
scoped inventory context.

**Submission is not ready.** PR #29 must remain draft until current required
checks pass and the real Supabase Table Editor screenshot is attached.
Local SQLite evidence is not a substitute for that screenshot.

## Rubric-to-implementation checklist

| Requirement | Exact implementation / proof | Status |
| --- | --- | --- |
| Eight-column Supabase table, UUID default, timestamp/event-type/GIN indexes, no update/delete workflow | `services/api/models.py` (`TelemetryEventRecord`); `services/api/migrations/20260923_create_telemetry_events.sql`; `services/api/tests/test_telemetry.py::test_table_has_the_required_columns_and_indexes` | Code reviewed; prior live verification recorded in PR #29; fresh Supabase evidence pending |
| Same `POST /telemetry/events` URL and count receipt | `services/api/routers/telemetry.py::receive_events`; `services/api/schemas.py::TelemetryReceipt`; `test_endpoint_persists_a_batch_and_logs_only_safe_metadata` | Automated coverage |
| Per-event validation and partial acceptance | `services/api/schemas.py::TelemetryIngestBatch`; `services/api/routers/telemetry.py::receive_events`; mixed-batch, non-object, invalid-envelope and invalid-property tests in `services/api/tests/test_telemetry.py` | Automated coverage |
| Reuse unchanged Phase 2 `TelemetryEvent` | `services/api/schemas.py::TelemetryEvent`; source comparison against merged capture baseline `origin/main` | No changes to class or validators |
| No frontend changes | `git diff --exit-code origin/main...HEAD -- uis` | No frontend diff |
| Correct technical and business event rows | `services/api/routers/telemetry.py::event_to_row`; `test_storage_mapping_preserves_allowlisted_tags_and_correlation`; `test_business_events_preserve_company_dimensions` | Automated coverage; live Supabase screenshot pending |
| Preserve allowlists and company dimensions | `docs/telemetry/event-schemas.json`; `docs/telemetry/telemetry-plan.md` section 9; `services/api/routers/telemetry.py::event_matches_catalogue`; business tests cover inbound/outbound in both `los_angeles` and `zaragoza` | Automated coverage, including numeric/type/enum/pattern/UUID/version rejection |
| One bulk insertion per batch | `services/api/routers/telemetry.py::persist_telemetry_events`; `test_valid_rows_use_one_bulk_insert_operation` | Statement-level regression coverage |

All test names above are in `services/api/tests/test_telemetry.py` unless
otherwise stated. The database-failure test additionally creates a real
duplicate-primary-key failure, confirms no partial batch survives, and proves
the rolled-back session can be used again. Empty batches store no rows.

## Evidence distinctions

PR #29 records a **previous** live Supabase verification with 34 events across
nine types, append-only client-role privileges, and this mixed-batch result:

```json
{"received": 2, "stored": 1, "rejected": 1}
```

Those historical observations must not be described as a fresh database audit.
On this review machine the Supabase project opens a sign-in screen, and the
previous user's local checkout and credentials are not available. No production
database migration, reseeding, or credential copying was performed.

### Fresh local verification

- `npm ci --no-audit --no-fund` and `npm run bootstrap`: passed.
- `npm run typecheck`: passed across every workspace.
- `npm run test`: 96 JavaScript/TypeScript tests and 362 API tests passed.
  The telemetry module accounts for 36 API cases, including 17 added during
  this review.
- `npm run build`: all packages and three production frontends passed.
  Next regenerated `jsx` in two frontend tsconfigs; only those generated
  edits were restored, preserving the zero-frontend-diff contract.
- `npm run lint --workspaces --if-present`: all three UI linters passed.
- `npm audit --omit=dev --audit-level=high`: zero vulnerabilities.
- `services/api/.venv/bin/python -m pytest packages/incident_analyzer/tests -q`: 10 passed.
- `ruff check .` and
  `ruff format --check services/api/tests/test_telemetry.py`: passed.
- Gitleaks v8.30.1 found no secrets in the storage branch's commits relative
  to `origin/main`. Scanning tracked working files flagged one pre-existing
  synthetic test-secret fixture in `services/api/tests/test_auth.py:540`;
  it is used exclusively by an environment-variable unit test, not a live
  credential. No `.env`, `.env.local`, dependencies, or virtual environments
  are tracked; the environment paths remain ignored.
- A real Chromium session against the production backoffice and local API
  performed failed login, successful login, inbound receipt, and outbound
  dispatch. The final synchronized run produced 14 new events across eight
  types in isolated SQLite before the manual mixed batch. A pre-run row
  boundary excluded historical events from these assertions. Browser page errors: zero. Company
  dimensions were preserved; generated login credentials, receipt reference,
  and tracking number were absent from stored telemetry. The manual request
  returned HTTP 200 and `{"received":2,"stored":1,"rejected":1}`; exactly
  one matching row persisted. These are local events, **not Supabase evidence**.

## Independent review and prerequisite integration

- Independent OpenAI/Sol reviewers assessed maintenance PR #33 and storage
  PR #29 in separate contexts. Maintenance had no actionable blockers and
  landed on main as `d60df41` after green CI; storage is synchronized with it.
  Both original memory-bank histories were retained during synchronization.
- The production dependency and repository-wide Ruff blockers described in
  the earlier review are resolved by that prerequisite. The storage PR still
  has no frontend diff against the updated main.
- Storage review found a genuine deployment defect: the backend image omitted
  the runtime catalogue required by `event_matches_catalogue`. The added COPY
  in `services/Dockerfile` ships the existing approved JSON at its expected
  path, without altering the catalogue or Phase 2 model.
- `test_backend_image_packages_the_runtime_catalogue` in
  `services/api/tests/test_telemetry.py` checks Docker COPY filesystem mapping
  and exercises actual endpoint ingestion against the staged catalogue.
  Temporarily omitting the COPY reproduced `FileNotFoundError`; restoring it
  passed. Independent re-review passed all 36 telemetry cases and cleared
  the deployment finding.
- This packaging test is **not Docker execution**. No Docker runtime is
  installed on this host, so an actual image build/run is not claimed.
  The storage assignment does not require a new Docker deliverable.
- The real Supabase Table Editor screenshot remains blocked by trusted login.
  Required GitHub checks must be green on the final pushed storage head.

## Submission and teacher demonstration

Submit **https://github.com/armonon/ai-engineering-company-project-monorepo/pull/29**
only after the draft gates are cleared.

1. Use the unchanged backoffice to register an inbound receipt and outbound
   dispatch, and produce a technical event such as a failed login.
2. Open Supabase Table Editor → `public.telemetry_events`; show at least five
   real rows, including technical and business types. Make `event_type`,
   `timestamp`, and the company dimensions in `tags` legible. Exclude secrets,
   account details, and unrelated data from the screenshot.
3. Demonstrate a mixed valid/invalid batch returning HTTP 200 with accurate
   `received`, `stored`, and `rejected`; verify only the valid event persisted.
4. Show the eight columns and three analytical indexes, the per-event parser,
   the single bulk insert, and the empty frontend diff.
5. Attach the real screenshot to PR #29, refresh the checks, and mark ready
   only after every required check and evidence item is complete.
