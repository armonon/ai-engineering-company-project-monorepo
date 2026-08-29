# Error handling audit

Audit of the TrackFlow monorepo against the tech lead's ticket: no error
should crash the app or leave the user in an undefined state, every async
frontend operation needs three visible states, user-facing messages must be
human-readable with a way forward, exceptions must be caught at the right
scope, and nothing sensitive may reach the client.

Scope: `uis/backoffice`, `uis/talent-pipeline-tracker`, `uis/website`,
`services/api`, `scripts/`, `packages/`.

Every finding below was **reproduced** before being written down — either by
probing the running API or by tracing a concrete value to the screen. The
severity ordering is by user impact, not by how easy it was to spot.

---

## CRITICAL

### C1 — An unhandled backend exception returns plain text, and the whole frontend assumes JSON

`services/api/main.py` registers no exception handler. Starlette's default for
an unhandled exception is the six-byte body `Internal Server Error` with
`content-type: text/plain`.

This is reachable, not theoretical:

```
POST /api/incidents/analyze   (CSV with one field larger than 128 KB)
  -> HTTP 500
  -> body: 'Internal Server Error'
```

Python's `csv` module raises `_csv.Error: field larger than field limit` and
nothing catches it. The upload comes from a drag-and-drop area in the
backoffice, so a real user with a large free-text column triggers it.

The consequence chains through the whole stack. Every frontend caller does
`res.json()`; on this body that throws
`SyntaxError: Unexpected token 'I', "Internal S"... is not valid JSON` — the
exact anti-pattern the ticket names.

**Fix:** register a global `Exception` handler returning a structured JSON body
with a generic message; log the real exception server-side only. Guard the
specific dangerous calls in the analyzer route as well (C2).

### C2 — The analyzer route leaves its two dangerous calls unguarded

`services/api/routers/incidents.py`

`read_csv_bytes(payload)` is wrapped only for `UnicodeDecodeError`; the
`csv` module's own `Error` (field size, embedded NUL, bad quoting) passes
straight through. `analyse(rows)` on line 97 is not guarded at all.

**Fix:** catch `csv.Error` alongside `UnicodeDecodeError` and return 400;
guard `analyse` and return 422 for data it cannot process.

### C3 — A render-time exception blanks the entire page

Neither Next app had an `error.tsx` or `global-error.tsx`, so there was no
error boundary anywhere. Any exception thrown while rendering unmounted the
whole tree and left Next's own fallback:

```
Application error: a client-side exception has occurred while
loading 127.0.0.1 (see the browser console for more information).
```

Reproduced by serving a 200 whose body was missing a nested object the
analyzer view reads (`data.totals.total_rows` → *Cannot read properties of
null*). The navigation vanished, the page was 127 characters long, and the
only instruction was to open a developer console.

This is the ticket's headline rule — "no error should crash the application
or leave the user in an undefined state" — failing in the most literal way.

**Fix, in two layers:**

1. Defensive reads in the analyzer result view, so a partial payload renders
   zeros instead of throwing (the ticket's optional-chaining and safe-default
   items).
2. `app/error.tsx` and `app/global-error.tsx` in both apps as the net for
   what nobody predicted — a human sentence, **Try again**, and a link home.
   Being route-scoped, the navigation stays on screen.

All three UIs now share Next.js 16.3.3 and the same `reset` error-boundary
contract. Keeping the copies aligned removes the former cross-major drift.

---

## HIGH

### H1 — Raw exception text is rendered to users in ~20 places

Both frontends do `err instanceof Error ? err.message : "fallback"` and put
the result on screen. The fallback is friendly; `err.message` is not. It
carries whatever the browser or the JSON parser produced:

| Real source | What the user sees |
|---|---|
| API host down | `Failed to fetch` |
| Plain-text 500 (C1) | `Unexpected token 'I', "Internal S"... is not valid JSON` |
| `readApiError` fallback (H2) | `{"field":"title","message":"Title is required."}` |

Sites: `LoginForm:41`, `RegisterForm:62`, `IncidentAnalyzer:82,396`,
`ProfileView:48`, `ResetPasswordForm:47`, `ChangePasswordForm:53`,
`IncidentList:102`, `QuoteCalculator:51`, `SupplierDirectory:38,65,81,454`,
`StatusStageControls:45,61`, `NotesPanel:31,52,65`, `CandidateList:44`,
`candidates/[id]/page:34`, `candidates/[id]/edit/page:34,89`,
`candidates/new/page:47`.

**Fix:** one shared translator that maps a thrown value to a human sentence,
used at every render site. Messages the server wrote for humans pass through;
transport and parser noise is replaced.

### H2 — `readApiError` falls back to `JSON.stringify(body)`

`uis/backoffice/lib/auth.ts`

When `detail` is neither a string nor an array the function returns the
stringified body. The incident manager returns exactly that shape —
`{"detail": {"field": ..., "message": ...}}` — so any caller that does not go
through `IncidentFieldError` shows the user raw JSON.

**Fix:** read `.message` out of an object detail; never stringify a body onto
the screen.

### H3 — The analyzer error panel shows a status code and offers no way forward

`uis/backoffice/components/IncidentAnalyzer.tsx:127`

```tsx
<p className="mt-1">HTTP {state.outcome.status}: {state.outcome.message}</p>
```

Renders as `HTTP 500: Analyse request failed (500).` — the status code twice,
no explanation, and the panel has no retry, no navigation, no support prompt.
The ticket requires every error state to offer an exit.

**Fix:** human sentence, no status code, and a retry that re-sends the file.

### H4 — `String(err.detail)` produces `[object Object]`

`uis/backoffice/components/IncidentAnalyzer.tsx:58`

`err.detail` is an object for every incident-manager validation error, so
`String()` yields `[object Object]`.

**Fix:** route it through the shared translator (H1).

### H5 — A login failure can echo the submitted password back to the client

`services/api/routers/auth.py:57-61`

```python
except Exception as exc:
    raise HTTPException(status_code=422, detail=f"Invalid login body: {exc}")
```

Two problems. The catch is `Exception` around a parse that only ever raises
`ValidationError` (verified — including for malformed JSON). Worse, Pydantic v2
errors embed the **input value** that failed, so when the password is sent as a
non-string JSON value the password itself comes back in `detail`:

| Body | Echoed in the response |
|---|---|
| `{"email": "a@b.com", "password": 123456}` | `123456` |
| `{"email": "a@b.com", "password": ["hunter2"]}` | `hunter2` |
| `{"email": "a@b.com", "password": {"p": "hunter2"}}` | `hunter2` |
| `{"email": "a@b.com"}` (missing) | nothing |

An unquoted numeric PIN is the realistic trigger. The value is returned to the
caller and lands in access logs.

**Fix:** catch `ValidationError` specifically and return a fixed message that
contains no part of the request body.

### H6 — A brief outage destroys a valid session

`uis/backoffice/components/AuthProvider.tsx`

```tsx
try {
  setUser(await fetchCurrentUser());
} catch {
  clearToken();      // <- any failure at all
  setUser(null);
}
```

The session check had two outcomes, signed in and signed out, so "we could
not ask" collapsed into "signed out". A network failure therefore **deleted a
valid token** and redirected to `/login`; the user had to sign in again even
after the API came back.

Found in the browser, not by reading: with the API stopped, the incident
manager rendered the sign-in page.

**Fix:** separate a real 401 (`UnauthorizedError` → sign out, correct) from a
transport failure (keep the token, render a recoverable state with Retry).
This is the same three-state pattern the ticket asks for, applied to the
session check itself.

---

## MEDIUM

### M1 — Raw `UnicodeDecodeError` text in an API response

`services/api/routers/incidents.py:83` — `detail=f"CSV must be UTF-8 encoded: {exc}"`
appends byte offsets and codec internals to a message a user reads.

### M2 — `scripts/analyze.py` leaves file I/O and CSV parsing unguarded

Line 58 `read_csv(args.csv)` and line 73 `args.out.write_bytes(data)` have no
handler. A directory instead of a file, a permissions error, a non-UTF-8 file,
or a read-only output path each produce a raw traceback. The `.exists()` check
on line 54 covers only the missing-file case.

The ticket asks for informative messages on `stderr` and a non-zero exit; a
traceback is neither.

### M3 — Overly broad catch around whole operations in both seeders

`scripts/seed_incidents.py:112` and `services/api/seed.py:221` wrap the entire
seed in `except Exception as exc` and print `{exc}`. This is the "single
try/except swallowing everything" shape the ticket calls out: a bug inside the
mapping logic is reported identically to a missing file, both exit 1, and the
message is whatever Python's exception text happened to be —
`[Errno 21] Is a directory: '...'` rather than advice.

(Echoing the *path* is fine in a CLI — the user typed it as an argument. The
problems are the undifferentiated catch, the errno noise, and the single exit
code. Unreadable input now exits 2 and a parse failure exits 1.)

### M4 — `res.json()` unguarded on success paths

`uis/backoffice/lib/suppliers.ts:83,93,103,116` and
`uis/backoffice/lib/incidents.ts:158,164,176,189` parse without a guard. A 200
with a truncated or non-JSON body throws a `SyntaxError` that reaches the UI
via H1.

### M5 — Raw transport exception text in the email service

`services/api/email_service.py:161-162` prints and returns
`f"transport error: {exc}"`. The exception from an HTTP client can include the
request URL and header names.

---

## LOW

### L1 — Silent failure loading the sample CSV

`uis/backoffice/components/IncidentAnalyzer.tsx:105` — `catch { /* ignore */ }`.
Deliberate and commented, but `?sample=1` failing silently leaves the user
looking at an empty page with no explanation.

### L2 — Non-string values coerced into an incident title

`packages/shared/.../model.py` `_clean` calls `str(value)`, so
`{"title": {"a": 1}}` is accepted and stored as the literal `"{'a': 1}"`.
Verified: returns 201. A defensive type check belongs with the other field
validation.

---

## Deliberately not changed

- **`uis/website`** is static; it has no async operations and needs nothing.
- **`packages/incident_analyzer`** raises precise exceptions and lets callers
  decide. That is correct for a library — the handling belongs at the route
  and script boundaries, which is where it was added.
- **422 responses from FastAPI's own request validation** are already
  structured JSON and are left as they are; the frontend translator turns them
  into readable text.

---

## Status

All findings above are fixed on `feature/error-handling-audit`, except where
noted as deliberately unchanged.

Backend, script, and validation findings are pinned by
`services/api/tests/test_error_handling.py` (19 tests). Each was written
against the broken behaviour first, and each was confirmed by reverting its
fix and watching the test fail.

Frontend findings are verified in a real browser against the running stack:
47 assertions covering the analyzer, the incident form, the supplier
directory, and a deliberately killed API, asserting that no page ever shows
`Unexpected token`, `Failed to fetch`, `[object Object]`, a raw HTTP status
code, a traceback, a filesystem path, or a raw JSON body — and that every
error state offers a way forward. H6 additionally asserts the token survives
an outage and that Retry recovers in place.
