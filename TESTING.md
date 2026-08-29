# TESTING.md

Test suite for the TrackFlow platform — AUTH-088, plus the two backlog
tickets API-042 and FE-019.

The regression that prompted this ticket was a refactor that broke token
expiration and locked users out for two hours. So the guiding question for
every test below is not "does this line execute?" but **"if someone broke
this, would a test fail?"** Coverage is reported, but it is the by-product,
not the goal.

---

## Running the tests

### Backend (pytest)

From `services/api/`:

```bash
uv run pytest
```

With coverage on the authentication module:

```bash
uv run pytest --cov=security --cov=services_users --cov=password_reset --cov=routes --cov-report=term-missing
```

### Frontend (Jest)

From `uis/backoffice/`:

```bash
npm test
```

With coverage:

```bash
npm test -- --coverage
```

### Everything at once

From the repo root:

```bash
npm run test
```

The root command runs every npm-workspace test and then the complete FastAPI
pytest suite. It uses `uv` when available and falls back to
`services/api/.venv` for an already-synchronised local environment.

---

## The test plan

Written before the tests, per the ticket. Each endpoint gets the three
tiers: **happy path**, **edge case**, **failure mode**.

A note on what is deliberately *not* here. The ticket says not to test HTTP
serialisation or framework internals, so there are no tests asserting that
FastAPI returns 422 for a missing body field, that Pydantic rejects a
malformed email, or that a response has a `content-type`. Those assert that
FastAPI works. Every case below asserts a decision **our** code makes.

### `POST /users` — register → `tests/test_register.py`

| Tier | Case | Why it matters |
|---|---|---|
| Happy | A new email creates a user, a linked profile, and a usable password | The whole point of the endpoint |
| Happy | The stored password is a bcrypt hash, never the plaintext | A leak of the database must not leak passwords |
| Edge | Email casing and surrounding whitespace are normalised | `Ana@x.com` and `ana@x.com ` must be the same account, or duplicates creep in |
| Edge | Password of exactly 72 bytes is accepted; 73 is rejected | bcrypt's input limit — see "boundary" below |
| Edge | Registering creates exactly one profile row, never two | |
| Failure | A duplicate email is a 409, and the original password still works | The failure must not damage the existing account |
| Failure | Twelve simultaneous registrations of one address produce one account | Check-then-act race; this one already bit us |

### `POST /auth/login` — → `tests/test_login.py`

| Tier | Case | Why it matters |
|---|---|---|
| Happy | Correct credentials return a token that identifies that user |
| Happy | Both accepted body shapes work (JSON, and the OAuth2 form Swagger sends) | Two parsers, two chances to diverge |
| Edge | Email lookup is case-insensitive and whitespace-tolerant | Must match registration's normalisation exactly |
| Edge | A password longer than bcrypt's 72-byte limit is rejected, not truncated | If it truncated, a longer string sharing a 72-byte prefix would authenticate |
| Failure | Wrong password, and unknown email, return the **same** message | Differing messages let an attacker enumerate accounts |
| Failure | A deactivated account cannot log in even with the right password |
| Failure | A corrupted stored hash is a failed login, not a 500 |

### JWT creation and validation → `tests/test_token.py`

This is the module the original regression lived in.

| Tier | Case | Why it matters |
|---|---|---|
| Happy | A freshly issued token resolves back to the user who owns it |
| Happy | `exp` is set from `ACCESS_TOKEN_EXPIRE_MINUTES` | The exact thing that broke |
| Edge | A non-numeric `ACCESS_TOKEN_EXPIRE_MINUTES` falls back to 60 instead of crashing at import |
| Edge | A token one second past expiry is rejected; one second before is accepted | Tests the boundary, not a comfortable midpoint |
| Failure | `alg: none` is rejected |
| Failure | A token signed with a different secret is rejected |
| Failure | A token with no `sub`, or a non-numeric `sub`, is rejected |
| Failure | A valid token for a since-deleted account is rejected |
| Failure | A `role` claim in the token cannot escalate privileges — the role is read from the database, not the token |

### `POST /auth/forgot-password` → `tests/test_forgot_password.py`

| Tier | Case | Why it matters |
|---|---|---|
| Happy | A registered address issues exactly one token, and only its hash is stored | A database leak must not yield usable reset links |
| Edge | An unknown address returns the identical body and status | Any difference is an account-enumeration oracle |
| Edge | A deactivated account issues no token but still returns 200 |
| Failure | A mail-delivery failure does not change the response | Otherwise a provider outage becomes an enumeration signal |

### `POST /auth/reset-password` → `tests/test_reset_password.py`

| Tier | Case | Why it matters |
|---|---|---|
| Happy | A valid token sets the new password, and the old one stops working |
| Edge | Consuming a token twice fails the second time | Single-use is the security property |
| Edge | Empty and whitespace-only tokens are rejected before any lookup |
| Edge | A record with an unparseable `expires_at` is rejected, not a 500 |
| Failure | An expired token is rejected |
| Failure | Unknown, used, and expired tokens all report **the same** reason | Otherwise a caller can probe which tokens existed |
| Failure | Resetting invalidates every other outstanding link for that account |

### `POST /auth/change-password` → `tests/test_change_password.py`

| Tier | Case | Why it matters |
|---|---|---|
| Happy | With the correct current password, the new one works and the old one does not |
| Edge | Changing the password invalidates any reset link already in flight |
| Edge | The 72-byte limit applies here too, not only at registration |
| Failure | A wrong current password changes nothing |
| Failure | The endpoint requires a token — no anonymous password changes |

### `GET /auth/me`

Covered in `test_token.py`, since every case is really a statement about
token validation.

---

## Backlog: API-042 — backoffice endpoints

Two non-authentication endpoint groups, same three tiers:

- **Suppliers** (`tests/test_suppliers_business_rules.py`, 17 tests) — the
  country/currency rule (USA→USD, Spain→EUR), rate validation, the closed
  category set, filter combinations, and route protection.
- **Incidents manager** (already covered by `tests/test_incident_manager.py`)
  — the status lifecycle, the CSV mapping, and summary aggregation.

## Backlog: FE-019 — frontend utilities

`uis/backoffice/__tests__/`, one happy path and one failure mode each:

- `toUserMessage()` — the error translator. Server messages pass through;
  browser and parser noise is replaced.
- `readJson()` — a malformed body must raise something human-readable, not
  `Unexpected token`.
- Token storage (`getToken` / `setToken` / `clearToken`) — must survive a
  `localStorage` that throws, as in private browsing.
- `formatRate()` / `CURRENCY_FOR_COUNTRY` — the supplier currency rule,
  which is duplicated on the frontend and must agree with the backend.
- `ALLOWED_TRANSITIONS` — the incident lifecycle, likewise duplicated.

---

## Results

### Backend — pytest

**318 backend tests pass** — including the inventory ORM coverage added after
AUTH-088 and API-042.

| Module | Tests | Endpoint |
|---|---|---|
| `test_register.py` | 13 | `POST /users` |
| `test_login.py` | 11 | `POST /auth/login` |
| `test_token.py` | 19 | JWT create/validate, `GET /auth/me` |
| `test_forgot_password.py` | 8 | `POST /auth/forgot-password` |
| `test_reset_password.py` | 12 | `POST /auth/reset-password` |
| `test_change_password.py` | 10 | `POST /auth/change-password` |

Shared fixtures live in `tests/conftest.py`; each test gets its own TinyDB
file so no test can see another's users.

Coverage on the authentication module — the ticket asks for **70%**:

```
Name                  Stmts   Miss  Cover
-----------------------------------------
security.py              68      0   100%
routers/auth.py           70      0   100%
password_reset.py        57      3    95%
services_users.py        85      7    92%
routers/users.py          28      1    96%
-----------------------------------------
auth module                          97%
```

Backoffice modules (ticket API-042 asks for **60%**):

```
routers/suppliers.py          56      0   100%
routers/incidents_manager.py  83      2    98%
routers/incidents.py          41      2    95%
```

`test_suppliers_business_rules.py` adds 17 tests on top of the existing
`test_suppliers_api.py`; the incident manager was already covered by
`test_incident_manager.py`.

Worth being straight about: coverage was already 90% before this ticket,
because the auth endpoints were built with tests. The 73 new tests moved
the number seven points. What they actually added is the **structure** the
ticket asks for — a module per endpoint, three tiers each — and the cases
below, which found three real bugs.

### Frontend — Jest

**35 tests pass** across three suites in `uis/backoffice/__tests__/`.

| Suite | Covers |
|---|---|
| `errors.test.ts` | `toUserMessage`, `readJson` |
| `token-storage.test.ts` | `getToken`, `setToken`, `clearToken` |
| `formatters.test.ts` | `formatRate`, `formatDate`, `humanCategory`, `CURRENCY_FOR_COUNTRY`, `ALLOWED_TRANSITIONS`, `BRANCH_LABELS` |

`npx jest --coverage` reports **46.5%** across `lib/`, and that number needs
an explanation rather than a defence. The uncovered lines are almost
entirely the `fetch` wrappers — `authFetch`, `fetchIncidents`,
`updateMyProfile` and friends. Testing those under Jest would mean mocking
`fetch` and asserting that the mock was called, which proves nothing about
whether the API agrees. They are covered instead by Playwright against a
running backend (see the error-handling PR). Of the code Jest is actually
the right tool for, `errors.ts` sits at **97%**.

---

## Bugs the tests found

The ticket asks for these to be written down. Three, all fixed in this
branch.

### 1. A mail-provider failure turned `/auth/forgot-password` into an account-enumeration oracle

Found by `test_a_mail_delivery_failure_does_not_change_the_response`.

The endpoint's entire security property is that its response never varies —
that is what stops a caller learning which addresses are registered. The
route trusted the sender to swallow its own failures, and the sender only
catches `httpx.RequestError`. Anything else — a misconfigured endpoint, a
bug in the message builder, an unexpected library error — escaped, so a
**registered** address returned 500 while an unknown one still returned
200. A provider incident would have handed an attacker a working oracle at
exactly the moment nobody was watching.

Fixed in `routers/auth.py`: the send is wrapped where the security property
lives. The reset token stays valid and the failure is logged server-side.

### 2. `formatRate` rendered "NaN €" to the user

Found by `formatters.test.ts`. `Intl.NumberFormat.format(undefined)`
returns the string `"NaN"`, so a supplier row with a missing rate printed
**NaN €** in the directory. Now returns an em dash.

The guard checks `Number.isFinite`, not truthiness — `0` is a legitimate
rate and a `||` fallback would have hidden it.

### 3. `formatDate` rendered "Invalid Date", and its error handling never ran

Found by `formatters.test.ts`. The function was wrapped in a `try/catch`
that could never fire: `new Date("nonsense")` does not throw, it returns an
Invalid Date, and calling `toLocaleDateString()` on that returns the
literal string `"Invalid Date"` — which is what the incident list showed
for any unparseable timestamp.

A catch block that looks like error handling and handles nothing. The
error-handling audit in the previous milestone walked past it; a test
caught it in one line. Now checks `Number.isNaN(date.getTime())`.

### 4. The supplier directory was readable without a token

Found by `test_the_directory_requires_authentication`.

Every **write** to `/suppliers` was protected. Both **reads** — the list and
the detail — were not, so TrackFlow's negotiated carrier rates and supplier
contact emails were available to anyone who could reach the API.

I first read this as an oversight, and that was wrong: `test_auth.py`
documented it as a deliberate exemption from AUTH-01, kept open so the
backoffice list would keep working *"until the frontend starts sending
tokens"*.

The point is that the condition has since been met. Every supplier call in
`uis/backoffice/lib/suppliers.ts` now goes through `authFetch`, so the
reason for the exemption has expired. Both reads are now protected, the old
test was rewritten to pin the closed state rather than deleted, and the
directory page was checked in a browser afterwards — it still loads for a
signed-in user, because the frontend was already sending the token.

Two other tests referenced the old behaviour and were updated with it.

---

## Where my own assumptions were wrong

Five tests failed on first run because *the test* was wrong, not the code.
Recording them because a test suite that only ever confirms what you
already believed is not doing much work:

- I expected two `forgot-password` requests to leave two live links.
  `issue_token` deliberately supersedes the old one — an old reset email
  sitting in an inbox is a live key to the account. The test now pins the
  safer behaviour.
- I expected a consumed token to be marked `used_at`. The route deletes
  the row outright, which is stronger — there is no spent-token record to
  leak. Test rewritten to assert "nothing usable remains".
- I asserted an exact `400` for a blank reset token. An empty string is
  caught by the request model (422), whitespace by our own check (400).
  Which layer refuses it is HTTP plumbing — the ticket says not to test
  that — so the test now asserts that it is refused and the password is
  untouched.
- I asserted `"4.9"` in a formatted euro amount. Euro renders in the es-ES
  locale, so it is `"4,90 €"`. The test now matches on digits, not
  punctuation.
- I called the public supplier reads an oversight before reading the test
  that documented them as a deliberate, time-limited exemption. The fix
  stands — the time limit had passed — but the reasoning in the first
  draft of this file was wrong.
- I hypothesised that login truncated passwords at bcrypt's 72-byte limit,
  which would have meant any longer string sharing a 72-byte prefix
  authenticated. Probed it directly: passlib rejects rather than
  truncates. No bug — but the boundary (71 and 72 accepted, 73 refused) is
  now pinned so a future change to the hashing library cannot quietly
  introduce one.

---

## AI-assisted workflow

Per the ticket, the agent was used for case discovery and boilerplate, not
for deciding what matters.

**What the agent surfaced that I had not planned.** After the plan above
was written, the endpoint source was handed over with the prompt "what
inputs could produce unexpected behaviour here?". The cases worth keeping
were:

- a stored password hash corrupted by a bad migration — does login fail, or
  does the endpoint 500?
- a valid, unexpired token for an account deleted since it was issued;
- a reset record whose `expires_at` is unparseable;
- a non-numeric `ACCESS_TOKEN_EXPIRE_MINUTES`, which would otherwise take
  authentication down at import time;
- the boundary *pair* around expiry — one second either side — rather than
  a single comfortably-expired token, which would pass even with the
  comparison inverted at the edge.

That last one is the difference between a test that guards the original
regression and one that only looks like it does.

**What was rejected.** Suggestions to assert status codes on malformed
request bodies, that a missing field returns 422, and that responses carry
the right `content-type`. All of those test FastAPI, not TrackFlow, and the
ticket rules them out.

**Boilerplate.** Fixtures, parametrisation, and the repetitive
arrange/act/assert scaffolding were generated, then read line by line —
which is how the five wrong assumptions above were caught: each was a
generated assertion that looked plausible and turned out to encode a belief
about the system that was not true.
