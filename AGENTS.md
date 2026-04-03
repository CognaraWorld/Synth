# Repository Agent Instructions

- Always create GitHub issues and pull requests against `https://github.com/CongaraWorld/Synth`.
- Do not open issues or pull requests against personal forks unless the user explicitly asks for that.
- If the local checkout is a fork or worktree of a fork, push the branch or open the pull request so the final review artifact appears in `CongaraWorld/Synth`.
- Follow more specific agent instructions from subdirectories such as `frontend/AGENTS.md` when working in those areas.
- For backend changes, keep API schema constraints and nullability aligned with the SQLAlchemy model definitions.
- Treat optional backend integrations and upload dependencies as degradable features: missing packages or transient init failures must not break unrelated app startup or routes.
- Never expose server-local filesystem paths in API responses; expose booleans, identifiers, or download endpoints instead.
- When backend logic assumes a single "primary" record, normalize duplicate rows defensively in read and write paths instead of assuming the database is already clean.
