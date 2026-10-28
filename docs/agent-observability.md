# TrackFlow real-time agent observability

The observability model separates three persistent entities:

- `ObservedAgent`: one stable registry row for `first_line_cx` or `rfp_pipeline`;
- `ObservedFlow`: one `chat_session` or `rfp_workflow` execution and its external
  trigger;
- `ObservedTask`: one ordered action in a flow, linked to its agent, trigger,
  previous/next task, and derived task ids.

An agent can participate in many flows, and a flow can include multiple agents, so
`ObservedFlowAgent` is a separate participation table. Task ids and flow ids—not
timestamps—form the causal chain, which keeps simultaneous flows from mixing.

## TrackFlow instrumentation

- The First-line CX API records `query` → `deliver` for every successful chat run.
- The RFP workflow records `query`, department `tool_call`, `draft_start`, `write`,
  `evaluate`, and `deliver` steps while retaining each `department_id`.
- `needs_intervention` is derived from the briefing: CX work stuck in `query` or
  `tool_call` for over 20 seconds, or an RFP with more failed evaluation passes than
  the configured retry limit.

Instrumentation is best-effort and never changes either agent's decision logic.

## Authenticated API and recovery stream

All `/observability/*` routes use the existing backoffice JWT. The API provides:

- registered agent list and agent detail with informational available actions;
- the last five flows and last ten tasks for an agent;
- paginated/filterable execution history;
- flow list/detail with ordered per-agent tasks;
- task trace reconstruction by id;
- SSE events `agent_step` and `agent_status_changed`.

SSE events are persisted before fan-out. The frontend uses authenticated
`fetch` + `ReadableStream`, sends `Last-Event-ID`, replays missed events, and
reconnects with progressive backoff. `EventSource` is not used.

## Design decisions

1. A trigger may be another task id or an explicit external reference such as
   `client_inbound_message:*` or `rfp_ticket:*`.
2. Flow identity scopes all tasks, so one agent can run several flows concurrently
   without combining their histories.
3. Available actions are calculated from status but rendered as non-clickable tags;
   Part 1 observes only. Part 2 can bind the same names to control endpoints.
4. Every task persists even when no browser is connected; the panel is a view over
   durable history, not the source of truth.
