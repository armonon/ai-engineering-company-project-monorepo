# Course completion audit

Audited: 2026-10-29

This document separates **technical evidence in the repository** from
**completion state in the 4Geeks learning platform**. A branch, test, or pull
request proves implemented work; it does not automatically mark a lesson,
practice, or project complete in the LMS.

## Repository evidence

`MILESTONES.md` is the canonical submission map. It covers the cumulative
company milestones and the advanced project sequence for data pipelines,
asynchronous processing, model training and RAG, agentic engineering, RFP
workflows, real-time controls, secure AI, and capstone preparation.

The audit found and remediated one clear project-level gap: the Google Play
review classifier. Its evidence is under `projects/playstore-naive-bayes/` and
includes:

- the official 891-row dataset and schema validation;
- deterministic stratified train, validation, and untouched test splits;
- Gaussian, Multinomial, and Bernoulli Naive Bayes implementations;
- Random Forest and Logistic Regression alternatives;
- development-only tuning and validation-only model selection;
- saved end-to-end inference pipelines, metrics, predictions, charts, and an
  executed notebook; and
- seven focused passing tests.

## Verification standard

A technical project is considered repository-ready only when its assignment
branch exists, the relevant focused tests pass, the root typecheck/test/build
gates pass, no credentials are tracked, and the branch or merged pull request
is recorded in `MILESTONES.md`.

This standard does not claim that an instructor has accepted the work or that
every LMS page has been opened. Instructor acceptance remains external state.

## Actions that remain student-owned

The following cannot be truthfully completed by repository automation:

1. Open each 4Geeks project page and submit the matching branch or pull-request
   URL from `MILESTONES.md`.
2. Complete or attest to readings and practices in the LMS. Existing code does
   not prove that a practice was personally completed.
3. Record the capstone video, answer the personal Q&A in the student's own
   words, choose the media-release option, and upload the permanent video link.
4. Respond to instructor feedback and resubmit only when the platform or
   instructor requests it.

The capstone script, demo sequence, recording checklist, and study guide are in
`docs/capstone/` and `docs/COURSE-STUDY-GUIDE.md`.
