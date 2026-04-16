# Repository Agent Instructions

- Always create GitHub issues and pull requests against `https://github.com/CognaraWorld/Synth`.
- Do not open issues or pull requests against personal forks unless the user explicitly asks for that.
- If the local checkout is a fork or worktree of a fork, push the branch or open the pull request so the final review artifact appears in `CognaraWorld/Synth`.
- Before any `git push` meant to update an existing PR, verify the PR head with `gh pr view <number> --json headRefName,headRefOid,headRepositoryOwner,isCrossRepository` and push to that exact repo/branch. Never assume `origin` is the correct remote.
- If the PR head branch lives in the upstream repository, push explicitly to `upstream/<branch>` even when the local branch is tracking `origin/<branch>`.
- Follow more specific agent instructions from subdirectories such as `frontend/AGENTS.md` when working in those areas.
- When a GitHub issue exists for the work, open the paired PR in the same execution pass once implementation is ready; do not leave a new implementation slice at issue-only state unless the user explicitly asks to pause before the PR.
- Every PR that corresponds to an issue must reference it with an explicit GitHub keyword in the PR body, such as `Closes #123` or `Refs #123`, not just plain issue text.
- For backend changes, keep API schema constraints and nullability aligned with the SQLAlchemy model definitions.
- Treat optional backend integrations and upload dependencies as degradable features: missing packages or transient init failures must not break unrelated app startup or routes.
- Never expose server-local filesystem paths in API responses; expose booleans, identifiers, or download endpoints instead.
- When backend logic assumes a single "primary" record, normalize duplicate rows defensively in read and write paths instead of assuming the database is already clean.
