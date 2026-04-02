# Contributing to Synth

This repository is the first product under Cognara World. The goal is to move fast without letting the codebase become inconsistent, fragile, or noisy.

Treat this document as the default contribution contract for everyone opening a branch or pull request.

## Core Rules

1. Preserve the product direction in `README.md` and `docs/IMPLEMENTATION_PLAN.md` unless Cognara World explicitly decides to change it.
2. Solve root causes. Do not ship band-aid fixes, speculative rewrites, or "good enough for now" patches that make later work harder.
3. Keep pull requests narrow and coherent. One PR should solve one issue, one feature slice, or one tightly related cleanup.
4. Match the existing architecture before introducing new abstractions.
5. Leave the codebase clearer than you found it.

## Repository Context

- `frontend/` is the Next.js dashboard and landing experience.
- `backend/` is the FastAPI API, meeting orchestration layer, and AI pipeline.
- `docs/` is the internal product and implementation reference.
- `frontend/CLAUDE.md` contains extra frontend-specific cautions. Read it before changing Next.js code.

## Before You Start

1. Read the relevant docs and feature files before editing.
2. Confirm the issue, bug, or feature scope you are solving.
3. Check whether another PR already covers the same work.
4. Pull the latest `main` and branch from it.
5. If the work is unclear or large, open a draft PR early instead of disappearing with a long-lived branch.

## Branching and Commit Hygiene

- Prefer branch names like `feature/...`, `fix/...`, `refactor/...`, `docs/...`, or `chore/...`.
- Keep commits focused and written in imperative mood.
- Avoid mixing refactors with behavior changes unless the refactor is required to make the fix safe.
- Do not rename, move, or delete large areas of the project without explaining why in the PR.

## Implementation Standards

### General

- Follow existing naming, file placement, and code style conventions.
- Use `Cognara World` for organization attribution in docs, UI placeholders, and repo guidance. Do not introduce personal author labels unless explicitly requested.
- Prefer simple, explicit code over clever abstractions.
- Remove dead code introduced by your change path.
- Never commit secrets, API keys, tokens, or personal environment values.
- If behavior changes, update the relevant docs in the same PR.

### Frontend

- Keep App Router structure predictable.
- Reuse shared UI primitives from `frontend/components/ui` before creating new ones.
- Keep page logic close to the route, and shared helpers in `frontend/lib` only when reuse is real.
- Preserve responsive behavior and avoid visual regressions.

### Backend

- Keep route handlers thin. Business logic belongs in the appropriate `core`, `context`, `meeting`, or `utils` module.
- Keep configuration in `app/config.py` and avoid scattering environment reads.
- Prefer explicit schemas and typed interfaces over ad hoc dictionaries where possible.
- Add or update tests when changing behavior.

## Verification Requirements

Run the narrowest relevant checks for the scope you changed:

- Frontend changes: run `npm run lint` from `frontend/`.
- Backend changes: run `pytest` from `backend/`.
- Full-stack contract changes: run both, plus a manual smoke test of the affected flow.
- Docs-only changes: verify paths, commands, filenames, and workflow instructions for accuracy.

If you could not run a relevant check, say so clearly in the PR and explain why.

## Pull Request Standard

Every PR must use the repository PR template and include:

1. The issue or problem being solved.
2. A link to the issue when one exists.
3. A proposed solution section that explains why this approach is correct and what tradeoffs were considered.
4. Verification steps with exact commands or manual test notes.
5. Risks, follow-ups, or known limitations.
6. Screenshots or recordings for UI changes when useful.

## Mandatory Review Workflow

These are merge gates, not suggestions:

1. The PR description must explicitly include `@copilot` as part of the team workflow.
2. The PR description must keep the `@copilot` mention as a team convention, and the author must also request Copilot review through GitHub's reviewer flow or rely on automatic Copilot code review if it is enabled for the repository or organization.
3. The PR author must read Copilot comments and either fix the issue or respond with a clear reason.
4. The author must request review from the other two owners.
5. When an owner reviews the PR, that owner has only two acceptable paths:
   - approve the PR and allow it to move toward merge if the change is ready
   - leave a PR comment with the exact concern, the requested change, and a specialized prompt the PR author can give to their LLM to address the concern correctly
6. Owner review comments must be concrete. Do not leave vague requests like "fix this" or "needs work" without a detailed concern and an actionable prompt.
7. If an owner requests changes, the PR author must address the concern, push the updated commits, and only then move the PR back toward merge.
8. The PR must receive approval from at least one of those two owners before merge.
9. All blocking comments and conversations must be resolved before merge.
10. Relevant verification must pass before merge.

No PR is merged before the Copilot review is handled, owner feedback is either approved or resolved through a repush, and at least one other owner approval is in place.

## GitHub Enforcement Settings

Use GitHub branch protection or rulesets to make this workflow enforceable instead of relying on memory alone:

1. Require a pull request before merging into `main`.
2. Require exactly 1 approving review before merge.
3. Dismiss stale approvals when new commits are pushed.
4. Require all conversations to be resolved before merge.
5. Enable Copilot code review automatically when available, or require contributors to request Copilot as a reviewer manually.
6. Add `CODEOWNERS` later if Cognara World wants explicit ownership by area.

## Review Expectations

Reviewers should focus on:

- correctness
- product fit
- architecture consistency
- maintainability
- security and secrets
- test coverage relative to the risk of the change

Approval means the reviewer believes the change is safe to merge, not just that it "looks fine."

## Merge Preference

- Prefer squash merges unless there is a strong reason to preserve branch history.
- Do a final skim of the rendered diff and PR description before clicking merge.
- If a PR creates follow-up work, open or link the follow-up issue before merging.

## Definition of Done

A contribution is done when:

- the scope is clear
- the implementation matches repo conventions
- relevant docs are updated
- relevant checks were run or explicitly explained
- Copilot review was requested through GitHub or automatic Copilot review is enabled
- `@copilot` feedback was reviewed by the author
- at least one of the other two owners approved
- there are no unresolved blocking comments

If any of those are missing, the PR is not ready to merge.
