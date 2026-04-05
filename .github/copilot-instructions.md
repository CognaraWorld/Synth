# GitHub Copilot Instructions for Synth

Use these instructions whenever you generate code, suggest changes, or review pull requests in this repository.

## Product and Repository Context

- This repository belongs to Cognara World.
- The product name is `Synth`.
- Synth is an AI meeting participant, not a passive transcription tool. It joins meetings, listens, answers when invoked, reasons over meeting context and uploaded documents, and can speak back into the meeting.
- The repository is split intentionally:
  - `frontend/` is the Next.js dashboard and landing experience.
  - `backend/` is the FastAPI API and AI pipeline.
  - `docs/` contains project guidance and implementation planning.

## First Principles

1. Prefer root-cause fixes over superficial patches.
2. Keep changes narrow, coherent, and easy to review.
3. Preserve architecture boundaries. Do not move logic across layers casually.
4. Match existing naming, structure, and conventions before introducing new abstractions.
5. Keep the repo name and product name as `Synth`.
6. Use `Cognara World` for organization attribution. Do not invent personal author names, maintainers, or sample ownership labels.

## Required Repo Context Before Suggesting Changes

- Read `README.md` and `docs/IMPLEMENTATION_PLAN.md` before making large or structural suggestions.
- If you are working in `frontend/`, read `frontend/CLAUDE.md` first because the Next.js version in use may differ from older training examples.
- Use the PR template and `CONTRIBUTING.md` as the review and process contract for this repository.

## Implementation Expectations

- Prefer robust fixes that improve long-term maintainability.
- Avoid drive-by refactors unless they are necessary to make the target change safe.
- Reuse existing components, utilities, and patterns before creating new ones.
- Keep docs in sync with behavior, setup, and workflow changes.
- Never suggest committing secrets, personal data, or environment-specific values.

## Review Expectations

When reviewing code, prioritize:

1. correctness
2. regressions
3. architecture consistency
4. security and secret handling
5. test coverage relative to change risk
6. documentation accuracy

Avoid low-value nitpicks unless they indicate a larger consistency problem.

## Verification Expectations

- For frontend changes, prefer `npm run lint` in `frontend/`.
- For backend changes, prefer `pytest` in `backend/`.
- For full-stack changes, recommend both plus a focused manual smoke test.
- For docs-only changes, verify paths, commands, filenames, and workflow steps.
- If verification cannot be completed, say so explicitly instead of implying certainty.

## Pull Request and Collaboration Expectations

- PRs should clearly state the issue being solved, the proposed solution, the reasoning behind it, the verification performed, and any risks or follow-ups.
- Keep the `@copilot` line in PR descriptions because that is part of this team's workflow.
- Also recommend requesting Copilot review through GitHub or enabling automatic Copilot code review, because that is the GitHub-native review path.
- Always resolve local Git conflicts and PR merge conflicts before requesting review or merge. Never leave conflict markers in committed files.
- Expect at least one approval from another owner before merge.
