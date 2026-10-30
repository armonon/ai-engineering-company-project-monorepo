# Project Brief — TrackFlow monorepo

## What TrackFlow is

TrackFlow is a last-mile delivery and warehouse management company
operating in the United States (Los Angeles) and Spain (Zaragoza), serving
mid-market e-commerce brands. The official company briefing is
[`BRIEFING.md`](../BRIEFING.md); see [`CONTEXT.md`](../CONTEXT.md) for the canonical domain
vocabulary and constraints — that file is authoritative; this one
gives the goal-level "why".

## What this monorepo is for

One repository, one company. Every deliverable across the course
milestones — public website, backoffice, TypeScript business-logic
modules, backend services, AI agents, data pipelines — ships from
here. The folder structure is the team structure: `uis/` is
frontend, `services/` is backend, `agents/` is AI product, and so on.

## Business objectives driving the current phase

1. **Sell more predictably.** Account managers need to run freight
   quotes on live customer calls without opening a spreadsheet. This
   is why the backoffice must render `packages/business-logic`
   output from day one.
2. **Look credible on the web.** The public site must be a real
   Next.js app, not a static mock — SEO, per-page metadata, and fast
   first paint matter because sales cycles start with a search.
3. **Move faster with AI without breaking things.** Every future
   milestone will lean on AI-assisted development. The infrastructure
   in `AGENTS.md`, `.agents/rules/`, and this memory bank is what
   keeps that speed from becoming rework.

## Problem this milestone solves

Before this milestone, the repo had code but no shared understanding.
An AI agent (or a new engineer) could not answer "what is TrackFlow?
what am I allowed to modify? what workflow do I follow before
committing?" without pulling one of us into chat.

Milestone 4 delivers:

- A memory bank that answers those questions in Markdown.
- An `AGENTS.md` that names the rules and the pre-commit workflow.
- One documented `.agents/rules/` rule with an explicit scope.
- One agent skill (`.agents/skills/freight-quote-invariants/`) that
  can be verified end-to-end.
- Two real Next.js apps under `uis/` — `website` (public) and
  `backoffice` (internal) — with the backoffice consuming the
  Milestone 2 business-logic package by import, not by copy.

## Success looks like

- A newcomer (human or AI) reads the memory bank + `AGENTS.md`, runs
  `npm run dev --workspace ./uis/website` and `--workspace ./uis/backoffice`,
  and sees TrackFlow branding + a working freight-quote form in
  under 10 minutes.
- Any change to the freight-quote formula happens in exactly one file
  and the backoffice picks it up automatically.
- The delivery workflow in `AGENTS.md` catches "generic company"
  drift before it hits `main`.
