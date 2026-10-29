# TrackFlow milestone branches

This is the canonical branch map for the 4Geeks TrackFlow coursework.
The repository stays cumulative on `main`; each milestone branch is a
stable submission snapshot from the same repository.

## Submission branches

| Milestone | Canonical branch | Deliverable | Provenance |
| --- | --- | --- | --- |
| 1 — Web fundamentals | `milestone-1-web-fundamentals` | TrackFlow public Next.js website | Reconstructed at the original website commit `c1212fe` |
| 2 — Programming fundamentals | `milestone-2-fold-in` | `@trackflow/programming-fundamentals` package and tests | Original merged PR #5 head `136b144` |
| 3 — Talent pipeline | `milestone-3-talent-pipeline` | Talent Pipeline Tracker under `uis/` | Original merged PR #4 head `f769ede` |
| 4 — AI-assisted engineering | `milestone-4` | Context, memory bank, agent rules, skills, website and backoffice | Original merged PR #1 head `d4af128` |
| 5 — Backend architecture | `milestone-5-strengthening` | Architecture proposal completed against the rubric | Original merged PR #6 head `d0d7a38`; initial draft remains on `milestone-5` |
| 5 — Inventory ORM | `milestone-5-inventory-orm` | SQLModel inventory API with PostgreSQL/Supabase support | Original merged PR #17 head `28caa9d` |
| 5 — Inventory backoffice | `milestone-5-inventory-backoffice` | Protected product, inbound, outbound, and movement views under `uis/backoffice` | Built as the stable assignment branch from accepted `main` |
| 6 — Incident analyser | `milestone-6-incident-analyzer` | Shared analyser, CLI, API and backoffice integration | Original merged PR #7 head `a396534` |
| 9 — Supplier directory | `milestone-9-supplier-directory` | FastAPI/TinyDB supplier directory and backoffice UI | Original merged PR #9 head `dcfb896` |

The older `milestone-2-programming-fundamentals` branch is retained as
the original draft. Use `milestone-2-fold-in` for the version integrated
into the monorepo architecture.

The Talent Pipeline Tracker's stable Milestone 3 submission remains on
`milestone-3-talent-pipeline`. The cumulative company app now also exposes
that complete workflow as the protected `/talent` section of
`uis/backoffice`, so the assessment demo can stay in one backoffice.

Both backend architecture and inventory ORM were genuinely assigned and
merged under the label "Milestone 5" in different coursework sequences. Use
the full branch name—not the number alone—when submitting or discussing one
of them. Do not rename either historical snapshot.

The warehouse-agent brief on `main` is intentionally unnumbered. The later
course pages organize work by named projects rather than stable milestone
numbers, so the advanced submission snapshots below keep their assignment
names and PR evidence instead of inventing numeric labels.

## Advanced course project branches

All of these branches were built from the same cumulative monorepo and merged
into `main`. Submit the named branch/PR that matches the assignment page.

### Implementing data pipelines

- Business pipeline design — `milestone-6-business-pipeline-design` ([PR #35](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/35))
- Veridian design exercise — `codex/veridian-pipeline-design` ([PR #36](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/36))
- Resilient pipeline — `milestone-6-resilient-pipeline` ([PR #40](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/40))
- Pipeline subflows/reporting — `codex/milestone-6-pipeline-enhancement` ([PR #42](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/42))

### Asynchronous processing and offloading

- Independent background process — `codex/background-processes-cronjob` ([PR #45](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/45))
- Triage priority queue — `codex/triage-queue` ([PR #47](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/47))
- Tagged branch queue — `codex/branch-queue` ([PR #48](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/48))
- Celery/Redis message queue — `codex/async-tasks` ([PR #49](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/49))

### Models training and RAG

- Google Play review classifier — `codex/models-naive-bayes-course-audit`
- Sales forecasting — `codex/sales-forecast-model` ([PR #50](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/50))
- Regression evaluation — `codex/regression-model-evaluation` ([PR #51](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/51))
- RAG knowledge base — `codex/rag-knowledge-base` ([PR #52](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/52))
- Review sentiment — `codex/models-sentiment` ([PR #65](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/65))
- Churn tuning — `codex/models-churn` ([PR #69](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/69))
- Image classifier — `codex/models-image-classifier` ([PR #71](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/71))

### Agentic engineering and workflows

- LangGraph migration — `codex/langgraph-agent-base` ([PR #53](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/53))
- External tools/routing — `codex/langgraph-agent-tools` ([PR #54](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/54))
- MCP company tools — `codex/mcp-company-tools` ([PR #55](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/55))
- Agent memory — `codex/agent-memory` ([PR #56](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/56))
- Harness/guardrails — `codex/agent-harness` ([PR #57](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/57))
- RFP intake/routing — `codex/rfp-intake` ([PR #58](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/58))
- RFP response generation — `codex/rfp-response-generation` ([PR #59](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/59))
- RFP approval/completion — `codex/rfp-approval-completion` ([PR #60](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/60))

### Real-time communication and secure AI

- Agent observability — `codex/agent-observability` ([PR #61](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/61))
- Pause/resume/cancel controls — `codex/agent-control` ([PR #62](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/62))
- Secure AI/NIST review — `codex/nist-ai-security` ([PR #63](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/63))
- OWASP audit/remediation — `codex/owasp-hardening` ([PR #64](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/64))
- Model dependency remediation — `codex/model-dependency-security` ([PR #74](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/74))

### AI engineering project delivery

- Capstone handoff package — `codex/capstone-handoff` ([PR #73](https://github.com/armonon/ai-engineering-company-project-monorepo/pull/73))

The 2026-10-28 submission audit verified that every branch named in this file
exists on `origin` and points to the exact head commit of its linked merged PR.
The final personal video, Q&A, media-release choice, and permanent upload remain
presenter-owned completion gates; they are not represented as a completed code
branch or LMS submission.

## Working rule

1. Start milestone work from the latest accepted `main`.
2. Create `milestone-<number>-<short-name>` in this repository.
3. Keep the work in the correct monorepo folder; do not create another
   repository for the same TrackFlow company.
4. Run the complete workflow in `AGENTS.md` before committing.
5. Push the milestone branch and submit that branch URL to 4Geeks.
6. Merge accepted work into `main`, but retain the milestone branch as
   the submission snapshot.

Run the read-only OpenClaw audit whenever the branch map needs checking:

```bash
COURSEWORK_REPO=. node ../4geeks-coursework-agent/.openclaw/skills/coursework-repository-audit/scripts/audit.mjs
```
