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

Both backend architecture and inventory ORM were genuinely assigned and
merged under the label "Milestone 5" in different coursework sequences. Use
the full branch name—not the number alone—when submitting or discussing one
of them. Do not rename either historical snapshot.

The warehouse-agent brief on `main` is intentionally unnumbered. Create its
milestone branch only after the 4Geeks project page supplies the official
milestone number and slug; the branch audit treats any guessed number as an
error.

No milestone-named branches or submissions for Milestones 7 and 8 were
found in the repository or pull-request history during the 2026-08-28
audit. Do not relabel later feature work as those milestones until the
corresponding 4Geeks assignment identifies the required deliverable.

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
