# Tech Context — TrackFlow monorepo

## Stack (current)

| Layer                    | Choice                                | Notes                                                        |
| ------------------------ | ------------------------------------- | ------------------------------------------------------------ |
| Package manager          | **npm** (workspaces)                  | One root `package.json` declares workspaces under `packages/*`, `uis/*`. |
| Frontend framework       | **Next.js 15** (App Router) + React 19 | Both `uis/website` and `uis/backoffice`. TypeScript strict, Tailwind v4. |
| Business-logic package   | **TypeScript** (`tsc` builds to `dist/`) | `packages/business-logic`, pure functions, unit-tested with `node --test`. |
| Package linking          | Workspace protocol (`"@trackflow/business-logic": "*"`) | Backoffice imports the package by name; no relative `../` reach across `uis/`. |
| Node                     | **≥ 20**                              | Enforced via `engines` in root package.json.                 |
| Backend services         | Not yet implemented                   | Landing in later milestones under `services/`.               |
| Persistence              | None yet                              | Business logic is pure; no database chosen.                  |
| CI                       | Not yet configured                    | Rule `MONO-2` covers the plan.                               |

## Repository layout (what matters right now)

```
./CONTEXT.md                     — authoritative company scenario (TrackFlow)
./AGENTS.md                      — the workflow every agent must follow
./memory-bank/                   — projectbrief, techContext, progress (this file)
./.agents/rules/                 — dev rules with explicit scopes
./.agents/skills/                — one-objective, verifiable agent skills
./packages/business-logic/       — Milestone 2 TypeScript module (freight quote)
./uis/website/                   — public corporate Next.js site
./uis/backoffice/                — internal Next.js app, imports @trackflow/business-logic
./services/, ./agents/, ...      — reserved for later milestones (READMEs describe intent)
```

## Architectural decisions taken in Milestone 4

1. **npm workspaces, not pnpm/yarn.** Rationale: matches the existing
   `packages/shared/package.json` shape and Node ≥20 ships npm out of
   the box in Codespaces. Reverse if a future workspace exceeds
   npm's install performance ceiling.
2. **Next.js 15 App Router for both UIs**, not one Next.js + one Vite.
   Rationale: consistency for account managers deploying the two
   apps; shared knowledge of Next primitives (metadata API,
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

## Active technical constraints

- **Currency and units** are frozen at the CONTEXT.md values (USD /
  EUR, km, kg). Rendering helpers must respect the tenant country;
  no hard-coded "$" symbols.
- **Priority service tier** is only valid when both origin and
  destination zones are `metro`, in either served country. Enforced in
  `packages/business-logic/src/freight-quote.ts` and re-enforced in
  the backoffice quote form.
- **Package builds must not depend on Next.js runtime.** Packages are
  plain Node / TypeScript.

## Known technical debt

- No CI workflow yet — captured under rule `MONO-2` as the next
  infrastructure task.
- `packages/shared/types` (`@repo/shared-types`) is untouched; the
  new work goes under `@trackflow/business-logic`. A follow-up may
  consolidate the two.
- No shared UI kit; `uis/website` and `uis/backoffice` each duplicate
  a `Button` component. Deferred until a third UI appears.

## Runbook

```bash
# once, after clone
npm install
npm run bootstrap        # builds packages/*

# during dev
npm run dev --workspace @trackflow/website
npm run dev --workspace @trackflow/backoffice

# before every commit (see AGENTS.md, Delivery Workflow)
npm run typecheck
npm run test
npm run build
```
