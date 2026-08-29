# Tech Context — TrackFlow monorepo

## Stack (current)

| Layer                    | Choice                                | Notes                                                        |
| ------------------------ | ------------------------------------- | ------------------------------------------------------------ |
| Package manager          | **npm** (workspaces)                  | One root `package.json` declares workspaces under `packages/*`, `uis/*`. |
| Frontend framework       | **Next.js 16.3.3** (App Router) + React 19 | Website, backoffice, and talent tracker share one patched major. |
| Business-logic package   | **TypeScript** (`tsc` builds to `dist/`) | `packages/business-logic`, pure functions, unit-tested with `node --test`. |
| Package linking          | Workspace protocol (`"@trackflow/business-logic": "*"`) | Backoffice imports the package by name; no relative `../` reach across `uis/`. |
| Node                     | **≥ 20.9**                            | Next.js 16 minimum, enforced by the root `engines`.          |
| Backend services         | **FastAPI**                            | Central API under `services/api`, managed with `uv`.          |
| Persistence              | **TinyDB + SQLModel/PostgreSQL**        | TinyDB covers existing local data; inventory uses PostgreSQL/Supabase. |
| Coursework agent         | **OpenClaw 2026.7.1+**                 | Dedicated agent uses this repository as its workspace.       |
| CI                       | **GitHub Actions**                     | PRs and `main` run bootstrap, typecheck, JS/Python tests, builds, and production audit. |
| Local containers         | **Docker Compose**                     | One UI container (website + backoffice) and one reloadable FastAPI container. |

## Repository layout (what matters right now)

```
./CONTEXT.md                     — authoritative company scenario (TrackFlow)
./AGENTS.md                      — the workflow every agent must follow
./memory-bank/                   — projectbrief, techContext, progress (this file)
./.agents/rules/                 — dev rules with explicit scopes
./.agents/skills/                — one-objective, verifiable agent skills
./MILESTONES.md                  — stable coursework branch and submission map
./IDENTITY.md / SOUL.md          — OpenClaw coursework agent identity and limits
./.openclaw/                     — allowlisted public warehouse-agent deliverables
./packages/business-logic/       — Milestone 2 TypeScript module (freight quote)
./uis/website/                   — public corporate Next.js site
./uis/backoffice/                — unified internal app: operations, inventory, talent, suppliers
./uis/talent-pipeline-tracker/    — historical Milestone 3 submission workspace
./services/api/                  — FastAPI auth, incidents, suppliers, and inventory
./docker-compose.yml             — two-service local development environment
./skills/                        — OpenClaw-visible reusable coursework skills
```

## Architectural decisions taken in Milestone 4

1. **npm workspaces, not pnpm/yarn.** Rationale: matches the existing
   `packages/shared/package.json` shape and Node ≥20 ships npm out of
   the box in Codespaces. Reverse if a future workspace exceeds
   npm's install performance ceiling.
2. **One patched Next.js major for all UIs**, not mixed framework majors.
   The original Milestone 4 choice was Next.js 15; the repository-hardening
   pass upgraded all three apps to 16.3.3 together. Rationale: consistency
   for contributors and one supported dependency graph; shared knowledge of Next primitives (metadata API,
   `next/image`, `next/font`). Cost: bigger dev-time footprint than
   Vite.
3. **Business logic as a workspace package**, not copied into
   `uis/backoffice/src/lib/`. Rationale: rule `MONO-1` — one
   authoritative implementation of the freight-quote formula. Cost:
   `tsc --build` must run before `next dev` on a fresh clone (root
   `npm run bootstrap` handles this).
4. **No global styling framework in `packages/`.** Tailwind is per
   app. Rationale: packages must stay UI-framework-agnostic so a
   backend service can consume them.
5. **All secrets remain out of the repo.** No `.env` committed; each
   app has an `.env.example`.
6. **Two development containers, one company repository.** The UI image runs
   the website and backoffice on ports 3000 and 3001 through `uis/start.sh`;
   the backend image runs the centralized FastAPI app on port 8000. Compose
   bind mounts source for hot reload and keeps dependencies/data in named
  volumes. Browser requests use the same-origin `/trackflow-api` and
  `/talent-api` paths; the backoffice Next.js server proxies them to the local
  backend and the 4Geeks Talent Tracker respectively.

## Active technical constraints

- **Currency and units** are frozen at the CONTEXT.md values (EUR /
  MXN, km, kg). Rendering helpers must respect the tenant country;
  no hard-coded "$" symbols.
- **Priority service tier** is only valid when both origin and
  destination zones are `metro` and country is `MX`. Enforced in
  `packages/business-logic/src/freight-quote.ts` and re-enforced in
  the backoffice quote form.
- **Package builds must not depend on Next.js runtime.** Packages are
  plain Node / TypeScript.
- **Environment files have separate scopes.** The root `.env` is consumed by
  Docker Compose; native FastAPI development loads only `services/api/.env` so
  container-only paths never leak into a host process.
- **UI linting uses native flat configs.** Next.js 16's exported configs are
  spread directly into each `eslint.config.mjs`; `FlatCompat` must not wrap
  them.

## Known technical debt

- No shared UI kit; `uis/website`, the cumulative backoffice, and the retained
  Milestone 3 snapshot still own their presentation components independently.
  Do not extract a component library until the interfaces actually converge.
- The warehouse agent is proven locally with an authenticated operative and a
  real acceptance transcript. Its private `.env`, OpenAI state, and session
  log remain outside Git; only the public contract and visible transcript are
  versioned.
- Milestones 7 and 8 and the warehouse agent's official milestone number
  remain unmapped until the 4Geeks project pages provide their identifiers.

## Runbook

```bash
# once, after clone
npm install
npm run bootstrap        # builds packages/*

# during dev
npm run dev --workspace @trackflow/website
npm run dev --workspace @trackflow/backoffice

# alternative: all applications with hot reload
cp .env.example .env
docker compose up --build

# before every commit (see AGENTS.md, Delivery Workflow)
npm run typecheck
npm run test
npm run build
```
