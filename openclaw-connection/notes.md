# Configuration notes

- The local OpenClaw gateway and the `4geeks-coursework` agent are installed and reachable.
- The agent uses the existing authenticated OpenAI Codex provider; no model key is stored here.
- SecretRefs are used for supported OpenClaw secrets, and no plaintext secret is tracked in Git.
- The current security audit has no critical findings; the gateway remains bound to loopback.
- Zapier MCP is OAuth-authorized and passes the OpenClaw connectivity probe.
- Zapier exposes Google Docs Create Document From Text and Google Calendar Create Detailed Event.
- The built-in Telegram plugin is enabled; a dedicated bot must still be connected before testing.
- Final screenshots and these notes will be updated only after the real workflow is verified.

