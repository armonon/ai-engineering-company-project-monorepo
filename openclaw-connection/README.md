# OpenClaw Connection — Submission Evidence

This folder contains the evidence package for the 4Geeks project
**Connect Your Agent: Telegram, Google Docs & Calendar**.

## Verified baseline

- OpenClaw `2026.7.1-2` is installed and the local gateway is running.
- The `4geeks-coursework` agent is registered against this monorepo.
- OpenAI is available through the existing authenticated Codex provider.
- The latest security audit reports no critical findings.
- The secrets audit reports no plaintext, unresolved, or shadowed secrets.
- Zapier MCP is OAuth-authorized and passes the OpenClaw connectivity probe.
- Zapier exposes only the required Google Docs `Create Document From Text` and
  Google Calendar `Create Detailed Event` actions for this project.
- The dedicated Telegram bot is connected, paired to the project owner, and
  routed to the `4geeks-coursework` agent.
- The agent uses the OpenClaw runtime for `openai/gpt-5.6-sol`, allowing the
  Telegram-routed conversation to use the approved Zapier MCP actions.
- The end-to-end acceptance run passed on October 26, 2026: the agent requested
  all five missing scheduling fields, created the Google Doc through Zapier,
  created the linked Calendar event through Zapier, and returned the usable Doc
  link in Telegram.

## Final evidence checklist

Save sanitized screenshots in this folder using these names:

1. `01-telegram-connected.png` — OpenClaw shows the Telegram channel connected.
2. `02-zapier-mcp-connected.png` — the Zapier MCP endpoint is active in OpenClaw.
3. `03-telegram-workflow.png` — the complete request, clarification, and completion conversation.
4. `04-google-doc-created.png` — the document created by the agent.
5. `05-calendar-event-created.png` — the linked review event created by the agent.

Before committing, crop or blur full names, email addresses, bot tokens, MCP
endpoint secrets, calendar invitees, and unrelated conversations.

## End-to-end acceptance test

Start with an intentionally incomplete Telegram request:

> Create a document for the TrackFlow inventory review and schedule time for me to review it.

The agent must ask for missing scheduling details. Reply with a title, date, time,
duration, and timezone using only the dedicated test account. The run passes only
when the agent creates both resources, provides a usable document link, and sends
a Telegram completion message.

The verified run used `TrackFlow Inventory Review - Final Assessment`, October
27, 2026, 3:00–3:30 PM, in `America/Los_Angeles`. The resulting document covers
LA and ZGZ stock review, inbound/outbound reconciliation, low-stock checks, a
decision log, and follow-up actions. The Calendar event is confirmed and embeds
the created document link in its description.

## Final verification

- [x] Telegram replies to a test message through the `4geeks-coursework` agent.
- [x] Zapier MCP exposes Google Docs create-document and Google Calendar create-event actions.
- [x] The generated document and calendar event exist in the dedicated Google test account.
- [x] `notes.md` contains five to ten accurate lines describing the completed setup.
- [ ] Every screenshot is readable and contains no credential or personal-data leakage.

The final checkbox remains a manual evidence-capture step because the screenshots
must be cropped or blurred before they are committed. Runtime verification is
complete; do not substitute unsanitized account screens for the required evidence.

