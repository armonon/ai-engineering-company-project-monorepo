# `skills` folder

This folder contains **agent skills** (reusable capabilities) that help you work consistently across the monorepo: research, data analysis, code review, scraping, math, and more.

- **Main purpose**: standardize how AI agents assist the team across the cross-functional project milestones.
- **Recommendation**: document each skill you add (when to use it, expected inputs/outputs, examples) and keep a clear subfolder structure so skills are easy to discover.

Coursework operations currently include read-only skills for milestone branch
auditing, 4Geeks authentication, project status, pending work, and progress.
See [`OPENCLAW.md`](../OPENCLAW.md) for the dedicated agent setup.

> _Spanish version: [README.es.md](./README.es.md)._


## Why there are two skills directories

| Directory | Holds | Read by |
|---|---|---|
| `skills/` (here) | agent skills — things an assistant does *for you* | OpenClaw |
| `.agents/skills/` | repository invariants — things that verify *this repo* | coding agents working on the monorepo |

`freight-quote-invariants` lives in `.agents/skills/` because it ships a
script that asserts the freight-quote rules still hold (rule `MONO-1`).
It is a check on the codebase, not a capability of an assistant.

