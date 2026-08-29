# AGENTS.md

> **Which AGENTS.md is this?** This one is the **repository contributor
> protocol** — the rules any human or AI contributor follows when
> changing code here. It is read by people and by coding agents working
> *on* this repo.
>
> It is **not** an OpenClaw agent contract. OpenClaw also reads a file
> called `AGENTS.md`, and expects an agent's hard limits in it. Those
> live with the agent they belong to:
>
> | Agent | Its config |
> |---|---|
> | Coursework Steward | `IDENTITY.md`, `SOUL.md`, `TOOLS.md`, `OPENCLAW.md` at the repo root |
> | Warehouse agent (planned) | `.openclaw/` — see `docs/BRIEF-warehouse-agent.md` |
>
> One filename, two meanings. Read the section headings below before
> assuming which contract you are holding.

Working protocol for any AI or human contributor operating in this
repository. This file is authoritative — if it conflicts with your
default habits, follow this file.

## 1. Read before you touch anything

At the **start of every session**, read these files in order:

1. [`CONTEXT.md`](./CONTEXT.md) — the TrackFlow company scenario.
2. [`memory-bank/projectbrief.md`](./memory-bank/projectbrief.md) — why
   this monorepo exists and what "done" looks like for the current
   phase.
3. [`memory-bank/techContext.md`](./memory-bank/techContext.md) — the
   stack, workspace layout, and current constraints.
4. [`memory-bank/progress.md`](./memory-bank/progress.md) — most
   recent changes and what was deferred.
5. Every file under [`.agents/rules/`](./.agents/rules/). Rule ids
   (e.g. `MONO-1`) are quoted in commit messages and PR descriptions
   when they apply.
6. The `README.md` of whichever top-level folder you're about to
   modify (`uis/`, `services/`, `packages/`, `agents/`, `skills/`,
   `.agents/`, `memory-bank/`).

Skipping this list is grounds for closing a PR unread.

## 2. Delivery workflow — mandatory before every commit

Every commit must have passed through **all five** of these steps in
order. Not four. Not "the ones that make sense." All five.

1. **Reconcile.** Run `git status` and read the diff of every staged
   file. If a change is not intentional, unstage it.
2. **Typecheck & test.** From the repo root:

   ```bash
   npm run typecheck
   npm run test
   ```

   Both must exit 0. If a test is failing because it's out of date
   for a deliberate behaviour change, update it in the same commit.
3. **Build.** From the repo root:

   ```bash
   npm run build
   ```

   Every workspace that has a `build` script must compile cleanly.
   New warnings count as failure — either fix them or explain
   them in the commit body.
4. **Update the memory bank.** If the commit changes runtime
   behaviour, folder structure, or a documented decision, edit
   [`memory-bank/progress.md`](./memory-bank/progress.md) — and
   `techContext.md` when the tech context itself moved — in the same
   commit. A behaviour change that ships without a memory-bank
   update is incomplete (rule `DOC-1`).
5. **Trace every diff.** In the commit body, cite either the memory
   bank, `CONTEXT.md`, or a rule id (`MONO-*`) that motivates each
   change. "Refactor" / "cleanup" alone is not enough — say what
   invariant is preserved and where it's written down.

## 3. Do NOT modify without explicit developer confirmation

These surfaces have downstream consequences that a coding agent
cannot verify on its own. If a task appears to require touching one
of them, **stop and ask** before editing:

- `CONTEXT.md` — the canonical company scenario. Renaming a domain
  concept here ripples through every workspace, every prompt, and
  every future service.
- Any file under `.agents/rules/` — changing a rule changes the
  contract other commits are supposed to comply with.
- `packages/business-logic/src/freight-quote.ts` — the freight-quote
  formula is a customer-facing invariant (see rule `MONO-1`).
  Changes require a paired update to the acceptance script under
  `.agents/skills/freight-quote-invariants/`.
- `package.json` (root) and workspace declarations — the workspace
  graph is the substrate every other tool assumes.
- Any file under `.git/`, `.github/`, or `.devcontainer/` — CI /
  deploy / dev-environment plumbing; wrong edits break every future
  contributor's session.

Everything else is fair game as long as the delivery workflow above
is honoured.

## 4. What to read next

- `.agents/rules/` — the specific conventions this repo enforces.
- `.agents/skills/` — reusable, verifiable procedures the agent can
  invoke instead of freehand.
- Each folder's own `README.md` — those describe intent and the
  right place to put the next file.
