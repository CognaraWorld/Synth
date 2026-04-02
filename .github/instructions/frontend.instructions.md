---
applyTo: "frontend/**/*.ts,frontend/**/*.tsx,frontend/**/*.js,frontend/**/*.jsx,frontend/**/*.mjs,frontend/**/*.css"
---

# Frontend Instructions

- This frontend uses Next.js App Router, React, Tailwind, and shared UI primitives under `frontend/components/ui`.
- Read `frontend/CLAUDE.md` before suggesting framework-specific changes. The installed Next.js version may differ from older examples.
- Prefer route-local page logic and shared reusable logic in `frontend/lib` only when reuse is real.
- Reuse existing UI components before introducing new primitives.
- Preserve responsive behavior and avoid brittle one-off styling.
- Prefer explicit TypeScript types over `any`.
- Keep API integration aligned with `frontend/lib/api.ts` unless the repository is intentionally changing that contract.
- If auth, routing, or API behavior changes, check for downstream effects across dashboard pages.
- For review comments, prioritize correctness, user flow regressions, data-fetching mistakes, and unnecessary client-side complexity over cosmetic nits.
