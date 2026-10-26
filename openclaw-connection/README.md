# OpenClaw Connection — Submission Evidence

This folder contains the evidence package for the 4Geeks project
**Connect Your Agent: Telegram, Google Docs & Calendar**.

## Verified baseline

- OpenClaw `2026.7.1-2` is installed and the local gateway is running.
- The `4geeks-coursework` agent is registered against this monorepo.
- OpenAI is available through the existing authenticated Codex provider.
- The latest security audit reports no critical findings.
- The secrets audit reports no plaintext, unresolved, or shadowed secrets.

The external integrations remain incomplete until the dedicated test accounts are
authenticated. They must not be represented as complete before the end-to-end
workflow has actually run.

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

## Final verification

- Telegram replies to a test message through the `4geeks-coursework` agent.
- Zapier MCP exposes Google Docs create-document and Google Calendar create-event actions.
- The generated document and calendar event exist in the dedicated Google test account.
- `notes.md` contains five to ten accurate lines describing the completed setup.
- Every screenshot is readable and contains no credential or personal-data leakage.

