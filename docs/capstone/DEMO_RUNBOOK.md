# Capstone demo runbook

## Demo path

Use one coherent story: **ModaViva RFP intake → routed drafts → human approvals →
final proposal → live observability and pause/resume**.

Recommended pages:

1. `/rfp`
2. `/observability`

Avoid touring every page. Inventory, telemetry, forecasting, and security are
supporting evidence if the reviewer asks questions, not separate demo chapters.

## Before recording

1. Pull `main` and confirm there are no local code changes required for the demo.
2. Start the existing services using the documented Docker Compose or native
   development path. Never display `.env` files or terminal history containing
   tokens.
3. Sign in with the prepared demo account.
4. Open the ModaViva RFP and complete one full practice run.
5. Confirm the RFP page shows intake, routing, drafts, approvals, and final
   proposal; confirm Observability shows the matching flow and task trace.
6. Reset to the prepared pre-approval state for recording.
7. Close unrelated tabs, silence notifications, enlarge browser text, and keep a
   fallback screenshot or already-completed flow ready.

## Recording sequence

- Start on camera for the hook.
- Cut to the RFP page already loaded; do not record installation or login.
- Use the prepared request so network/model latency does not consume the pitch.
- Point to evidence and state, not raw logs.
- Demonstrate one approval and one live control only.
- Return to camera for the engineering decision and all three Q&A answers.

## Failure fallback

If a provider is slow during the take, show the persisted completed flow and say
that the workflow is durable across external latency. Do not fake a successful
request, expose credentials, or edit the video to imply an action occurred when
it did not.

## Evidence ready for questions

- Evidence-only RAG refusal path and retrieval evaluation.
- Checkpointed LangGraph RFP state with independent department approvals.
- Typed, read-only MCP tools and tenant-scoped access controls.
- Persisted SSE traces and authenticated WebSocket controls.
- Prompt-injection tests, rate limiting, OWASP audit, and non-root containers.
