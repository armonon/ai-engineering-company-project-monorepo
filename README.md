# TrackFlow AI Engineering Coursework Monorepo

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_One cumulative TrackFlow repository for the AI Engineering Career Program — 4Geeks Academy._

_Estas instrucciones tambien estan disponibles en [espanol](./README.es.md)._

**Live public demonstration:**
[trackflow-coursework-demo.armonon.chatgpt.site](https://trackflow-coursework-demo.armonon.chatgpt.site)

The hosted demonstration publishes the canonical `uis/website` landing page.
Run Docker Compose for the authenticated backoffice and FastAPI demonstration.

---

## Purpose

This repository is the canonical home for the **TrackFlow transversal project**. Every accepted milestone is integrated into `main`, while its submission snapshot remains available on a milestone branch.

- Read [`MILESTONES.md`](./MILESTONES.md) before choosing a branch.
- Treat [`CONTEXT.md`](./CONTEXT.md) as the canonical TrackFlow company context.
- Use [`AGENTS.md`](./AGENTS.md), `skills/`, and directory-level README files as working guidance.
- The coursework agent lives in its own repository: [4geeks-coursework-agent](https://github.com/armonon/4geeks-coursework-agent).

---

## How to start

1. **Clone this repository** or open it in Codespaces.
2. **Read** `AGENTS.md`, `CONTEXT.md`, `MILESTONES.md`, and the memory bank.
3. **Fetch branches** and select the milestone named by the current assignment.
4. **Start from the latest accepted `main`** when creating a new milestone branch.
5. **Implement in the correct folder** — do not dump work in the root or create another TrackFlow repository.
6. **Run the complete verification workflow** before committing or submitting.

---

## Running it after a fresh clone

**Order matters.** The frontends import `@trackflow/business-logic`, a
workspace package whose compiled `dist/` is git-ignored. Building a UI
before that package is linked and compiled fails with
`Module not found: Can't resolve '@trackflow/business-logic'`.

```bash
# 1. From the REPO ROOT — links the npm workspaces
npm install

# 2. From the REPO ROOT — compiles packages/*/dist
npm run bootstrap
```

Only then are the UIs buildable/runnable:

```bash
npm run dev:website       # http://localhost:3000
npm run dev:backoffice    # http://localhost:3100
```

The backend is a separate, `uv`-managed project:

```bash
cd services/api
uv sync            # installs deps + the local incident-analyzer package
uv run seed        # loads the CONTEXT suppliers into TinyDB
uv run uvicorn main:app --reload    # http://127.0.0.1:8000/docs
```

> Running `npm install` *inside* `uis/backoffice` alone is not enough —
> npm workspaces are linked from the root.

### Docker development environment

Run the public website, backoffice, and FastAPI service together:

```bash
cp .env.example .env
docker compose up --build
```

- Website: <http://localhost:3000>
- Backoffice: <http://localhost:3001>
- API docs: <http://localhost:8000/docs>

The UI container runs the two Next.js workspaces through `uis/start.sh`.
The backend container runs Uvicorn with reload enabled. Source folders are
bind-mounted for hot reload, while dependencies and local development data
stay in named volumes. The committed `.env.example` contains only safe local
defaults; `.env` remains ignored and must never contain committed secrets.

---

## How to think about this monorepo

You are building **one company** across many milestones and projects. Each top-level folder has a **single responsibility** — like a real engineering team repo.

| Layer               | Folders                           | What lives here                                                  |
| ------------------- | --------------------------------- | ---------------------------------------------------------------- |
| **Company context** | `CONTEXT.md`                      | Domain facts, field names, constraints for your assigned company |
| **User-facing**     | `uis/`, `services/`               | Frontends and backends users (or operators) interact with        |
| **Data**            | `data/`                           | Raw files, pipelines, processed datasets, evaluation sets        |
| **AI**              | `agents/`, `skills/`, `mcps/`     | Agents, reusable agent capabilities, MCP tool servers            |
| **Automation**      | `workflows/`                      | n8n flows and cross-system orchestration                         |
| **Reuse**           | `packages/`, `shared/`            | Shared types, SDKs, schemas, templates                           |
| **Operations**      | `infra/`, `scripts/`, `internal/` | Docker, deploy configs, one-off scripts, internal CLIs           |
| **Documentation**   | `docs/`                           | Architecture, decisions, conventions for the whole repo          |

**Rule of thumb:** if it has a UI → `uis/`. If it exposes an API or runs in the background → `services/`. If it moves or transforms data → `data/`. If an AI model does the work → `agents/` (+ `skills/` or `mcps/` as needed).

---

## Current status

This is an active monorepo, not an unused template. It contains the TrackFlow
public website, backoffice, talent tracker, shared TypeScript packages,
FastAPI services, incident analysis, authentication, and supplier management.
The root npm workspace provides aggregate typecheck, test, and build commands.

Milestone submission branches are catalogued in `MILESTONES.md`. Milestones 7
and 8 are intentionally marked unmapped until their 4Geeks requirements are
confirmed.

---

## Folder guide — what goes where

Read the linked `README.md` inside each folder before you start coding there.

### Root files

| Path                         | Purpose                                                                   | What you do here                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| [`CONTEXT.md`](./CONTEXT.md) | Shared TrackFlow context and scoped-precedence rules                     | Read it before changing domain models, product copy, or business rules                                         |
| `.github/workflows/ci.yml`   | Required monorepo verification                                             | Runs Node and Python checks for pull requests and `main`                                                       |
| `README.md` / `README.es.md` | This guide                                                                | Orientation — you are here                                                                                    |

### `uis/` — user interfaces

**Purpose:** All frontend applications — anything a human sees and clicks.

**Put here:**

- Public website (`website/`)
- Internal admin / backoffice (`backoffice/`)
- Customer portals, loyalty apps, Streamlit/Gradio tools, dashboards with a UI

**Examples:** corporate landing page, operations backoffice, loyalty portal, telemetry dashboard UI

→ See [`uis/README.md`](./uis/README.md)

### `services/` — centralized company API (FastAPI)

**Purpose:** One **centralized FastAPI backend** for the whole company — a single entry point that keeps complexity low as the project grows.

**Put here:**

- One main FastAPI app (e.g. `api/`) with routers/modules per domain (locations, menus, sales, telemetry, etc.)
- Background workers only when they truly need to run separately from the API

**Recommendation:** avoid splitting into many microservices early. Add endpoints to the same FastAPI app; extract a worker only when necessary.

**Examples:** `/locations`, `/menus`, `/sales/reports`, webhook handlers, scheduled jobs

→ See [`services/README.md`](./services/README.md)

### `data/` — datasets, pipelines, and evaluation

**Purpose:** Everything data-related, from raw files to production-ready tables.

| Subfolder                                       | Purpose                      | What you do here                                                          |
| ----------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------- |
| [`data/raw/`](./data/raw/README.md)             | Untouched source data        | Store dumps, exports, sample CSVs/JSON — document origin and PII rules    |
| [`data/pipelines/`](./data/pipelines/README.md) | ETL/ELT jobs                 | Write ingestion, cleaning, and transformation scripts                     |
| [`data/process/`](./data/process/README.md)     | Clean / intermediate outputs | Save artifacts produced by pipelines (features, aggregates, clean tables) |
| [`data/eval/`](./data/eval/README.md)           | Quality measurement          | Golden sets, RAG/agent eval datasets, experiment metrics                  |

**Flow:** `raw` → `pipelines` → `process` → consumed by `services/`, `uis/`, or `agents/`. Use `eval` to prove quality.

### `agents/` — AI agents

**Purpose:** Autonomous or semi-autonomous AI assistants for the company.

**Put here:**

- One subfolder per agent (e.g. `support-agent/`, `onboarding-agent/`)
- Agent config, prompts, tools wiring, tests
- Start from [`agents/_template/`](./agents/_template/README.md) when creating a new agent

**Examples:** customer support bot, employee onboarding copilot, training assistant

→ See [`agents/README.md`](./agents/README.md)

### `skills/` — reusable agent capabilities

**Purpose:** Packaged instructions + scripts that agents (or you in Cursor) reuse across the repo.

**Put here:**

- Skills for data analysis, code review, scraping, research, etc.
- Each skill = a folder with `SKILL.md`, optional scripts and resources

**Example included:** `skills/data-analysis/` (pandas cleaning script + metrics reference)

→ See [`skills/README.md`](./skills/README.md)

### `mcps/` — Model Context Protocol servers

**Purpose:** Bridge AI models to your systems — databases, APIs, GitHub, custom tools.

**Put here:**

- One subfolder per MCP server (e.g. `database-mcp/`, `github-mcp/`)
- Tool definitions, resources, and server config

**When to use:** when an agent needs live access to data or actions your codebase alone cannot provide

→ See [`mcps/README.md`](./mcps/README.md)

### `workflows/` — automation and orchestration

**Purpose:** Connect systems without writing full apps — scheduled jobs, webhooks, notifications.

**Put here:**

- n8n workflow exports, Make/Zapier configs, or orchestration docs
- Flows that link `services/`, `data/pipelines/`, and `agents/`

**Examples:** new-order → Slack alert, nightly ETL trigger, lead → CRM sync

→ See [`workflows/README.md`](./workflows/README.md)

### `packages/` — shared libraries

**Purpose:** Versionable code reused by multiple apps, agents, or pipelines.

**Put here:**

- Shared TypeScript types (`packages/shared/` → `@repo/shared-types`)
- UI component libraries, API clients, analytics SDKs

**Rule:** if `uis/` and `services/` both need the same interface → extract it here

→ See [`packages/README.md`](./packages/README.md)

### `shared/` — loose shared assets

**Purpose:** Resources that are not a full package — schemas, templates, static assets, short docs.

**Put here:**

- JSON schemas, email templates, OpenAPI specs, design tokens
- Anything reused but too small or non-code for `packages/`

→ See [`shared/README.md`](./shared/README.md)

### `docs/` — cross-cutting documentation

**Purpose:** Architecture and decisions that span the whole company project.

**Put here:**

- System architecture diagrams, ADRs, security/observability guides
- Conventions not tied to one app or agent

→ See [`docs/README.md`](./docs/README.md)

### `infra/` — infrastructure and deployment

**Purpose:** How the company project runs in Docker, cloud, or CI.

**Put here:**

- Dockerfiles, Terraform, K8s manifests, Nginx configs, CI/CD pipelines

Local container orchestration lives in the root `docker-compose.yml`, where it
coordinates `services/` and `uis/` over the named TrackFlow development
network.

→ See [`infra/README.md`](./infra/README.md)

### `scripts/` — helper scripts

**Purpose:** Small, repeatable automation — not full apps.

**Put here:**

- Setup scripts, seed data generators, lint wrappers, one-off migrations
- Document each script: what it does, args, and how to run it

**Difference from `internal/`:** scripts are usually single files; `internal/` tools are structured projects with their own deps and tests.

→ See [`scripts/README.md`](./scripts/README.md)

### `internal/` — internal developer tools

**Purpose:** Robust utilities for the engineering team.

**Put here:**

- CLIs, packaged migration tools, prompt evaluators
- Tools with their own `package.json`, tests, and install steps

→ See [`internal/README.md`](./internal/README.md)

---

## Where should I put this?

Quick decision guide:

```text
Does it have buttons and screens?          → uis/
Does it run on a server / API / queue?     → services/
Is it raw or transformed data?             → data/raw/ or data/process/
Does it move data between systems?         → data/pipelines/
Do you measure AI/pipeline quality?        → data/eval/
Is it an AI assistant with a goal?         → agents/
Is it a reusable AI capability/instruction?→ skills/
Does AI need to call external tools/APIs?  → mcps/
Is it n8n / scheduled automation?          → workflows/
Will 2+ folders import the same code?      → packages/
Is it a schema/template/asset, not a lib?  → shared/
Is it architecture or team-wide docs?      → docs/
Is it docker-compose for local dev?        → repo root
Is it Docker / deploy / cloud config?      → infra/
Is it a one-off script?                    → scripts/
Is it a CLI tool with its own package?     → internal/
```

---

## Repository structure (tree)

```text
ai-engineering-company-project-monorepo/
├── README.md / README.es.md   # This guide
├── CONTEXT.md                 # Canonical TrackFlow context and scoped overrides
├── .github/workflows/ci.yml   # Required Node + Python verification
├── uis/                       # Frontends (website, backoffice, dashboards)
├── services/                  # Centralized FastAPI company API
├── data/
│   ├── raw/                   # Source datasets
│   ├── pipelines/             # ETL/ELT jobs
│   ├── process/               # Clean / intermediate outputs
│   └── eval/                  # Evaluation sets and metrics
├── agents/                    # AI agents (+ _template/ starter)
├── skills/                    # Reusable agent skills
├── mcps/                      # MCP servers for tool access
├── workflows/                 # n8n and automation flows
├── packages/                  # Shared libraries (@repo/shared-types, …)
├── shared/                    # Schemas, templates, loose assets
├── docs/                      # Architecture and cross-cutting docs
├── infra/                     # Docker, Terraform, deployment
├── scripts/                   # Helper scripts
└── internal/                  # Internal CLIs and dev tools
```

---

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alesanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._
