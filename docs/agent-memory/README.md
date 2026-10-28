# TrackFlow agent memory and self-improvement

## Architecture

TrackFlow keeps three data responsibilities separate:

| Store | Purpose | Write policy |
| --- | --- | --- |
| Qdrant `trackflow_knowledge` | Approved company policy and reference documents | Loader-managed, never changed by agent conversations |
| SQLite `agent_memory.db` | User-approved operational corrections and recurring preferences | Only the consent resolver writes approved or safely edited proposals |
| SQLite `agent_traces.db` | Append-only execution evidence | Every graph node appends a sanitized event |

The memory database path comes from `AGENT_MEMORY_DB`. Records are isolated by
authenticated user id. The API supplies that id; clients cannot choose another
memory owner.

## Interaction contract

1. `memory_decision` checks for one pending proposal for this user. The next
   message is classified as `approve`, `reject`, `edit`, or `ambiguous` before
   any new question is processed.
2. An explicit approval writes the proposed fact. An edit must still pass the
   same category and safety evaluation. Rejection, ambiguity, and 24 hours of
   silence keep an audit record but write no memory.
3. `memory_lookup` reads approved, unexpired memories and adds relevant facts
   to the graph context.
4. The normal routed RAG/tool answer is produced.
5. `memory_review` evaluates the interaction. If the message meets an explicit
   criterion, the answer includes a proposal and asks for a separate decision.
   This node never writes memory.

Only one proposal may be pending per user. If the decision message also
contains a question (`Approve and what is the escalation policy?`), TrackFlow
records the decision and continues the graph with that question.

## Explicit evaluation criteria

The TrackFlow company briefing allows only:

- corrected carrier assignment or coverage rules;
- causes of demonstrably recurring incidents (not single packages);
- recurring B2B monthly-report preferences.

The evaluator refuses exact B2C addresses, internal warehouse routes/docks,
tracking identifiers, active commercial negotiations, one-off incidents, and
anything outside those three classes. Neither raw passwords nor service tokens
are fields in the schema.

## Consolidation and retention

Memories are consolidated by `(user, category, scope)`: an approved correction
replaces the older fact rather than adding contradictory copies. Recurring
incident context expires after 14 days, carrier rules after 180 days, and B2B
report preferences after 365 days. Expired records are deleted on reads; an
unanswered proposal is marked `silence_rejected` after 24 hours. Each user is
capped at 100 active records, retaining the newest.

## Demonstration

Run the focused acceptance suite:

```bash
services/api/.venv/bin/pytest -q \
  tests/pipelines/test_agent_memory.py \
  tests/pipelines/test_agent_graph.py \
  services/api/tests/test_agent.py
```

The suite demonstrates a complete approved cycle, a complete rejected cycle,
safe edits, ambiguity, a future recall, per-user isolation, the pending-proposal
constraint, and continuation after a decision plus another question.

