# TrackFlow warehouse agent

This is the public, submission-safe OpenClaw workspace for the warehouse
agent described in [`../docs/BRIEF-warehouse-agent.md`](../docs/BRIEF-warehouse-agent.md).
It is deliberately separate from the repository-root `4geeks-coursework`
agent: coursework coordination and physical-inventory write authority do not
share one agent identity.

## Public contract

- `IDENTITY.md` — the agent's warehouse role.
- `AGENTS.md` — non-negotiable inventory safety constraints.
- `TOOLS.md` — authenticated API surface and helper commands.
- `skills/stock-check/SKILL.md` — read-only SKU resolution and stock checks.
- `skills/log-movement/SKILL.md` — confirmation-gated receipts, dispatches,
  and losses.
- `TRANSCRIPT.md` — exact visible messages from a real authenticated
  acceptance session.

`skills/_shared/inventory-api.mjs` is a small command-line adapter. It logs in
for each invocation, keeps credentials and bearer tokens out of output, and
never retries a write. It has no dependency outside Node.js.

## Private local configuration

Create `.openclaw/.env` locally; it is denied by the repository's allowlist
and must never be force-added:

```dotenv
TRACKFLOW_API_ORIGIN=http://127.0.0.1:8000
TRACKFLOW_API_EMAIL=<operative account email>
TRACKFLOW_API_PASSWORD=<operative account password>
```

Do not put a bearer token in the repository. The helper obtains a short-lived
token from `/auth/login` for each command and never prints it.

## Local runbook

From the repository root:

```bash
docker compose up --build -d
docker compose exec backend seed-inventory
openclaw agents add trackflow-warehouse --workspace "$(pwd)/.openclaw" --non-interactive
openclaw agents set-identity --agent trackflow-warehouse \
  --workspace "$(pwd)/.openclaw" --from-identity
openclaw models --agent trackflow-warehouse auth login --provider openai
```

Then ask the agent a read-only question:

```bash
set -a
source .openclaw/.env
set +a
openclaw agent --local --agent trackflow-warehouse \
  --message "How many white sneakers do we have in LA?"
```

`--local` keeps the private workspace variables in that one agent process.
Do not pass credentials on the command line or copy them into the global
OpenClaw configuration. The existing OpenAI login remains in OpenClaw's
private agent state.

Writes always take two turns. The first response must restate the exact SKU,
quantity, warehouse, and movement type; only a subsequent explicit approval
permits the API call.

## Credential and transcript rules

The root `.gitignore` denies every other `.openclaw/` path by default. Never
force-add `.env`, credentials, tokens, local memory, session databases,
generated state, or a fabricated transcript. `TRANSCRIPT.md` is regenerated
only from a real API-backed session.
