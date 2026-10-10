---
name: warehouse-agent
scope: always-active
applies-to:
  - "**"
description: Keep Warehouse Steward inventory operations inside the confirmed, authenticated HTTP API boundary.
---

# Warehouse agent rule

Follow `AGENTS.md`, `TOOLS.md`, and the selected inventory skill exactly.
Reads must be fresh. Writes require a later explicit confirmation, use the
authenticated HTTP adapter once, and are never retried after an uncertain or
refused result.
