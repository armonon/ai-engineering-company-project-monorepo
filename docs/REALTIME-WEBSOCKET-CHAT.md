# TrackFlow First-line CX WebSocket chat

The existing First-line CX agent remains unchanged. The new communication
boundary binds one authenticated WebSocket to a `ChatSession` with
`agent_id = first_line_cx`, then publishes explicit events on the session's
channel: `session_snapshot`, `user_message`, `token_chunk`,
`generation_interrupted`, and `generation_completed`.

## Interrupt and recovery verification

1. Sign in and open `/support`.
2. Ask a TrackFlow shipment or returns question and confirm the assistant text
   grows chunk by chunk.
3. While it is responding, type a correction and choose **Interrupt and
   redirect**. Confirm the partial response remains visible with an
   **Interrupted** label and the corrected response appears as a new turn.
4. Reload or briefly disconnect the browser. The client reconnects after 0.5,
   1, 2, 4, 8, then 10 seconds using the same `session_id`; the first frame is
   a `session_snapshot` containing the prior user, interrupted assistant, and
   redirected assistant messages.

Automated tests additionally assert that no `token_chunk` for the cancelled
message is published after `generation_interrupted`.

## Design decisions

- WebSockets are required because client interruption travels upstream while
  response chunks continue downstream. SSE cannot carry that bidirectional
  control message.
- One producer task runs per `session_id`. Any number of sockets can subscribe
  to the same in-process pub/sub channel, so a supervisor sees the identical
  event stream without triggering a second agent call.
- Stream abort is an `asyncio.Task.cancel()`, not LangGraph HITL
  `interrupt()`. Cancellation stops publication before the redirected turn is
  created. The partial assistant message is checkpointed as `interrupted`, and
  `new_input` becomes a separate user message with a separate assistant turn.
- The secured agent graph completes its output guard before chunks are exposed.
  The transport remains cancellable while delivering those chunks, preserving
  TrackFlow's existing guardrails rather than streaming unvalidated model text.
