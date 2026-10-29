# Configuration notes

- The local OpenClaw gateway and the `4geeks-coursework` agent are installed and reachable.
- The agent uses the existing authenticated OpenAI Codex provider; no model key is stored here.
- SecretRefs are used for supported OpenClaw secrets, and no plaintext secret is tracked in Git.
- The current security audit has no critical findings; the gateway remains bound to loopback.
- Zapier MCP is OAuth-authorized and passes the OpenClaw connectivity probe.
- Zapier exposes Google Docs Create Document From Text and Google Calendar Create Detailed Event.
- The dedicated Telegram bot is connected, paired, and routed to the `4geeks-coursework` agent.
- Telegram turns use the model-scoped OpenClaw runtime so both approved Zapier actions are available.
- The original Telegram run asked for title, date, start time, duration, and timezone before creating anything.
- A fresh October 28 audit run used both Zapier write actions without failures to create the replacement TrackFlow review Doc and confirmed October 29, 2026 Calendar event with the current Doc link.
