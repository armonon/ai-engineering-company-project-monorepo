# TrackFlow real-time agent controls

Operational controls extend the observability model without changing the RFP
business-approval graph.

## State and guarantees

- `paused` is resumable. The flow/agent participation stores a checkpoint with
  the last completed task, previous status, and capture time.
- `cancelled` is terminal. Resume is rejected, the flow is cancelled, and any
  still-pending/running child tasks for that agent are marked cancelled.
- Commands are serialized by an agent+flow lock and increment `control_version`,
  so simultaneous operators cannot interleave state transitions.

For `first_line_cx`, pause holds the chat execution open. For `rfp_pipeline`, the
checkpoint records the existing `rfp-{ticket_id}:{department_id}` LangGraph thread
ids from the approval workflow. Resume retains that checkpoint and continues the
same task chain; it never creates a new flow or replays intake.

## Authentication, audit, and pub/sub

The backoffice opens `/observability/control`, authenticates with its existing JWT,
then subscribes to one `agent_id` + `flow_id`. `actor_id` is derived from the token;
the command payload cannot provide or override it.

Every accepted `pause`, `resume`, or `cancel` is appended to `ObservedTask` with
`actor_id` and timestamp. `control_applied` is broadcast to every socket subscribed
to the execution. Reconnecting clients receive a fresh `control_state` snapshot
containing status, version, and checkpoint, preventing UI desynchronization.

Business approval remains visibly distinct: `waiting_for_human` describes the RFP
owner decision, while pause/resume/cancel are engineering/operations kill-switch
actions that can coexist with it.

## Design decisions

1. Pause and cancel cannot be aliases: pause must retain a resumable checkpoint;
   cancel must prevent all future nodes and resume attempts.
2. A per-execution lock plus transition validation makes two simultaneous commands
   deterministic.
3. Cancelling a parent flow cancels only pending/running tasks belonging to that
   targeted execution; other agents and flows are untouched.
4. WebSocket authentication happens before subscribe/control, and all actor identity
   is server-derived.
