# RFP response generation and evaluation

Part 2 starts exclusively from the persisted Part 1 handoff:

```text
ticket_id + metadata + department workstreams/key_aspects
```

The response graph does not read the uploaded PDF. It sets the existing ticket to
`drafting`, runs the applicable TrackFlow department generators in parallel, then
sets `under_evaluation` while three isolated evaluators review each section:

- readability: minimum length and a documented Flesch-Kincaid threshold;
- relevance: department-specific required aspects;
- compliance: TrackFlow briefing rules for currency, numeric on-time SLA,
  48-hour minimum returns processing, volume-discount table, and carrier-rate
  confidentiality.

Each evaluation is persisted as a structured object with `readability`,
`relevance`, `compliance`, `overall_pass`, and `feedback_for_generator` fields.
Failed sections return to their own generator with that feedback. Passing sections
remain unchanged while other departments retry.

The loop is capped at three attempts. On exhaustion, the final draft and evaluation
are retained, the section and ticket are marked `needs_human_review`, and the
section remains in the Part 3 handoff. A ticket is never discarded because a draft
could not self-correct.

## API and backoffice

`POST /rfp/tickets/{ticket_id}/generate` returns `202` and runs the graph in the
existing backend. The backoffice button is shown only for `intake_complete`
tickets, polls active work, and surfaces the draft plus all evaluator outcomes.

## Verification

```bash
services/api/.venv/bin/python -m pytest -q \
  tests/pipelines/test_rfp_response.py services/api/tests/test_rfp.py
npm run typecheck --workspace @trackflow/backoffice
npm run test --workspace @trackflow/backoffice -- --runInBand
```
