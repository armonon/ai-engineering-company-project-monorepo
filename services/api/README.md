# `services/api`

TrackFlow's backend. One FastAPI service, routes grouped by domain —
the modular-monolith shape proposed in
[`../../docs/ARCHITECTURE_PROPOSAL.md`](../../docs/ARCHITECTURE_PROPOSAL.md).

```
services/api/
├── main.py               FastAPI app: CORS + router mounting
├── models.py             Pydantic models (supplier directory)
├── database.py           TinyDB initialisation
├── seed.py               initial-data loader  →  uv run seed
├── routes/
│   ├── suppliers.py      supplier directory endpoints
│   └── incidents.py      incident-report analysis endpoints
└── tests/                46 tests
```

## Quick start

```bash
cd services/api
uv sync            # installs deps + the local incident-analyzer package
uv run seed        # load the CONTEXT suppliers into TinyDB
uv run uvicorn main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>


## Authentication

Stateless JWT. No sessions, no cookies. `User` and `Profile` live in
**TinyDB only** — other stores reference the TinyDB user `id` as
`user_uuid` and never hold a copy of the account.

### Setup

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # paste as SECRET_KEY
```

`SECRET_KEY` has no default on purpose: a fallback would mean tokens
signed with a publicly-known key. The app refuses to mint or verify a
token without it.

| Variable | Purpose |
| -------- | ------- |
| `SECRET_KEY` | JWT signing secret. Required. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime. Defaults to 60. |

### Endpoints

| Method | Endpoint | Access |
| ------ | -------- | ------ |
| `POST` | `/auth/login` | public — email + password, returns a JWT |
| `GET` | `/auth/me` | protected — credentials + linked profile |
| `POST` | `/users` | **public** — registration; creates the linked Profile too |
| `GET` | `/users` | protected |
| `GET` | `/users/{id}` | protected — self or admin |
| `PUT` | `/users/{id}` | protected — self or admin; `role` is admin-only |
| `DELETE` | `/users/{id}` | protected — self or admin; cascades to the Profile |
| `GET` | `/profiles/me` | protected — resolved from the token |
| `PUT` | `/profiles/me` | protected — owner only |

`POST /auth/login` accepts an OAuth2 form (so Swagger's **Authorize**
button works) or a JSON body with `email` + `password`.

### Model split

`User` holds credentials only: `id`, `email`, `hashed_password`,
`is_active`, `role`, `created_at`. Display name and contact data —
`name`, `phone`, `address` — live on `Profile`, linked one-to-one via
`user_id`. A test asserts the stored user record contains nothing else.

`role` accepts `admin`, `manager`, or `user`. Registration always
produces `user`: `role` is not a field on `UserCreate`, so it cannot be
set by the caller.

### Passwords

Hashed with bcrypt via `libpass` (a maintained drop-in fork of
`passlib`; the import path is still `passlib.hash`). Plain text never
reaches TinyDB — asserted by a test that greps the stored record.
Passwords over 72 bytes are rejected rather than silently truncated.

### Which routes are protected

Twelve endpoints require a valid token. Six of them sit outside
`/users` and `/auth`, exceeding the required five:

| Route | Why |
| ----- | --- |
| `POST /suppliers` | creates directory data |
| `PATCH /suppliers/{id}/rate` | changes commercial terms |
| `PATCH /suppliers/{id}/status` | suspends/activates a contract |
| `DELETE /suppliers/{id}` | destroys a record |
| `POST /api/incidents/analyze` | processes an uploaded incident file |
| `GET /api/incidents/results/export` | exports analysed incident data |

`GET /suppliers` and `GET /suppliers/{id}` stay public so the
backoffice list keeps working until the frontend starts sending
tokens. `GET /` is the health check.

### 401 vs 403

- **401** — no token, malformed token, bad signature, expired token, or
  a token whose account was deleted or deactivated.
- **403** — the caller is authenticated but acting on someone else's
  account, or a non-admin trying to change a `role`.


## Password reset and change (AUTH-03)

| Method | Endpoint | Access |
| ------ | -------- | ------ |
| `POST` | `/auth/forgot-password` | public — **always 200** |
| `POST` | `/auth/reset-password` | public — consumes a single-use token |
| `POST` | `/auth/change-password` | protected — verifies the current password |

### Email provider

**Resend** (<https://resend.com>). Chosen over SendGrid because its
shared onboarding sender (`onboarding@resend.dev`) delivers to the
account owner's address in development **without** verifying a domain
in DNS — the step that most often blocks this exercise.

Set the key in `services/api/.env`:

```
RESEND_API_KEY=your_key_here
```

The API intentionally loads only `services/api/.env`. The root `.env` is for
Docker Compose and can contain container-only paths that are invalid during a
native `uv run uvicorn ...` session.

**Without the key the flow still works**: the reset link is printed to
the server log instead of being emailed, clearly labelled so it cannot
be mistaken for real delivery. That keeps the whole journey testable
locally with no credentials.

| Variable | Purpose |
| -------- | ------- |
| `RESEND_API_KEY` | Resend API key. Unset → console fallback. |
| `EMAIL_FROM` | Sender. Defaults to Resend's onboarding sender. |
| `FRONTEND_BASE_URL` | Where the reset link points. Defaults to `http://localhost:3100`. |
| `RESET_TOKEN_EXPIRE_MINUTES` | Link lifetime. Defaults to 30, clamped to 5–120. |
| `ALLOWED_ORIGINS` | Optional comma-separated browser origins. Explicit origins only; `*` is rejected. |

### Why tokens are stored server-side

A JWT carrying only an `exp` claim **cannot be invalidated after use** —
anyone holding it could replay it until expiry. So each issued token
gets a row in the `password_resets` table recording its expiry and
whether it has been used, and the row is marked used the moment a reset
succeeds.

What is stored is the **SHA-256 hash** of the token, never the token
itself: a database leak does not hand an attacker a working reset link.
The same reasoning that applies to passwords.

Also enforced:

- Requesting a new link **invalidates the previous one**, so an old
  email stops being a live key to the account.
- Changing the password invalidates every outstanding reset link.
- Unknown, expired, and already-used tokens all return an **identical**
  400, so a caller cannot probe which tokens ever existed.
- The check-then-mark-used sequence holds a lock, so two simultaneous
  submissions of the same link cannot both succeed.

### No enumeration

`/auth/forgot-password` returns the same 200 and the same body whether
or not the address is registered. Combined with the identical 401 on
login for unknown-email vs wrong-password, neither endpoint can be used
to discover which addresses have accounts.


## Incident manager

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `POST` | `/api/incidents` | Register an incident. 400 naming the bad field. |
| `GET` | `/api/incidents` | List, filterable by `status`, `origin`, `branch`, `category`. |
| `GET` | `/api/incidents/summary` | Totals by status, category, origin, and branch. |
| `GET` | `/api/incidents/{id}` | Detail. 404 if unknown. |
| `PATCH` | `/api/incidents/{id}/status` | Advance the lifecycle. 400 on an illegal transition. |

All five require a valid token.

### Lifecycle

`open → in_progress → resolved`, with `discarded` reachable from either
non-final state. `resolved` and `discarded` are final. An illegal
transition returns 400 whose message says what *is* allowed from the
current state, so the caller can recover without reading the spec.

### Validation errors

Every validation failure returns 400 with
`{"detail": {"field": ..., "message": ...}}` so the UI can put the
message next to the offending input. No endpoint returns a stack trace.

### Shared domain rules

The value sets, the lifecycle, and the CSV transformation live in
[`packages/shared`](../../packages/shared) (`trackflow_shared`), which
both this service and `scripts/seed_incidents.py` import. Neither owns
a private copy, so the seeded data and the API cannot disagree about
what is valid.

Row-level CSV validity is *not* re-implemented either — the shared
package calls `validate_record` from `incident_analyzer`, written for
the analyzer milestone.

### Seeding history

```bash
uv run seed-incidents
```

Loads `scripts/incidents-trackflow.csv` as `origin: "customer"`
incidents, applying the CONTEXT transformations. Idempotent (matched on
the CSV's `incident_id`), and every rejected row is reported with its
reason rather than dropped silently.

Against the shipped CSV: **95 inserted, 5 rejected**, and the summary
then matches the CONTEXT expected totals exactly — status 29/52/14 and
category 14/45/19/17.

## Supplier directory

Data model, valid categories, allowed statuses, and the seed data all
come from [`../../CONTEXT.md`](../../CONTEXT.md). Field names are not
paraphrased anywhere.

| Method   | Endpoint                       | Purpose                                                       |
| -------- | ------------------------------ | ------------------------------------------------------------- |
| `POST`   | `/suppliers`                   | Register a supplier. Returns it with its TinyDB id. → `201`    |
| `GET`    | `/suppliers`                   | List all. Optional `?country=` and `?category=` filters.       |
| `GET`    | `/suppliers/{id}`              | Detail. → `404` if unknown.                                    |
| `PATCH`  | `/suppliers/{id}/rate`         | Update the rate and stamp `updated_at`. Rejects `<= 0`.        |
| `PATCH`  | `/suppliers/{id}/status`       | Activate / suspend. Only the two CONTEXT statuses.             |
| `DELETE` | `/suppliers/{id}`              | Remove. → `404` if unknown.                                    |

Filters combine with AND, so
`/suppliers?country=Spain&category=carrier_last_mile` answers *"what
last-mile carriers do we have in Spain?"*.

### Validation

Everything is rejected by Pydantic **before it reaches TinyDB**:

| Rule | Result |
| ---- | ------ |
| `status` outside `{active, suspended}` | `422` |
| `rate_per_shipment` zero or negative | `422` |
| `categories` empty, or a value outside the eight CONTEXT categories | `422` |
| `currency` disagreeing with `country` (USA→USD, Spain→EUR) | `422` |
| Missing a required field | `422` |

`updated_at` is system-generated — it is absent from the input models,
so a client cannot set it. It is written on create and re-stamped on
every rate change, which is the audit trail Carlos needs.

### Storage

TinyDB, a JSON file at `services/api/data/trackflow.json`. It is
git-ignored because the seeder regenerates it; run `uv run seed` after
cloning. Data persists across restarts — covered by
`test_data_survives_a_server_restart`.

## Seeder

```bash
uv run seed
```

Loads the 15 suppliers from CONTEXT.md and reports what it did:

```
  inserted ......... 15
  already present .. 0
  total in database  15
```

Idempotent — it matches on supplier name, so running it twice inserts
nothing the second time. Every seed row is pushed through the same
`SupplierCreate` model an API request uses, so if the CONTEXT data ever
drifts from the model the seeder fails loudly instead of writing junk.

## Incident analysis

Carried over from the previous milestone, now mounted as a router:

| Method | Endpoint                            |
| ------ | ----------------------------------- |
| `POST` | `/api/incidents/analyze`            |
| `GET`  | `/api/incidents/results/export`     |

## Tests

```bash
uv run pytest
```

169 tests — 52 for the incident manager, 51 for auth, 20 for password
reset/change, 39 for the supplier directory, and 7 for incident
analysis.

## Telemetry verification receiver

`POST /telemetry/events` is the Phase 2 non-persistent stub. It accepts
`{"events": [...]}`, validates every standard envelope, logs only the batch
count and `event_type` labels, and returns `{"received": N}`. It never logs
event properties or writes them to a database. The future target is declared
with `TELEMETRY_ENDPOINT` in the untracked `.env` file so Phase 3 can replace
the implementation without changing browser callers.

Authentication responses also include an HMAC-pseudonymised
`telemetry_user_id`. Set a dedicated `TELEMETRY_HMAC_KEY` in `.env`; raw TinyDB
user ids, email addresses, and credentials are never used as telemetry ids.

## CORS

Explicit origins for the `uis/*` dev servers, including the containerized
backoffice on port 3001, never `"*"`. Override the defaults with a
comma-separated `ALLOWED_ORIGINS` value. The Compose backoffice normally uses
the same-origin `/trackflow-api` proxy, so its requests do not require CORS.
