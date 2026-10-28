# RFP approval and completion

Part 3 consumes the Part 2 handoff and creates one independently checkpointed
LangGraph branch for each active TrackFlow department. Branch identity is always:

```text
rfp-{ticket_id}:{department_id}
```

Each branch records a trace entry before the human gate, calls LangGraph
`interrupt`, and persists state in SQLite. `resume` uses `Command(resume=...)` on
that exact thread; it never restarts generation. Warehouse, Last Mile, and Reverse
Logistics therefore remain independently resumable. Approving department B does
not move or unblock department A.

The accepted decisions are `approve`, `reject`, and `request_changes`. Only the
briefing's fixed owner is recorded as approver. Change requests run the matching
department generator and structured evaluators again, then pause at the same human
gate. This loop is capped at two revisions; exhaustion preserves the draft and
returns `needs_human_review`.

## Fixed arbitration

The explicit arbitration step reads structured metadata/section state and implements
the exact TrackFlow triggers:

- `volume-vs-capacity`: Miguel Torres caps Last Mile volume to Warehouse capacity;
- `returns-sla-breach`: Sofía Ramos (Reverse) or Miguel Torres forces changes;
- `currency-mismatch`: Miguel Torres rewrites the offending quote to US→USD or
  Spain→EUR.

No LLM or department vote resolves these conflicts.

## Completion

The existing ticket remains `waiting_for_approval` while any branch is interrupted.
Only after every active section is `approved` does the synthesizer store one
`FinalRfpDocument`, transition the ticket to `done`, and expose the proposal in the
existing backoffice and API.

## Reproducible Parts 1-3 run

```bash
services/api/.venv/bin/python scripts/rfp_workflow_e2e.py \
  path/to/trackflow-request-1.pdf \
  --ticket-id modaviva-e2e \
  --output /tmp/modaviva-e2e-proposal.md
```

The script uses the real PDF intake, response generation/evaluation, persistent
interrupts, simulated decisions from the named owners, and final synthesis.
