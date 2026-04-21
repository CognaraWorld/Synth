# AI Meeting Participant Bot Dashboard

Production-ready SaaS dashboard skeleton built with Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn-style components, Prisma, NextAuth, TanStack Query, Zustand, and a standalone WebSocket transcript server example.

## Quick start

```bash
npm install
cp .env.example .env
npm run prisma:generate
npm run db:push
npm run prisma:seed
npm run dev
```

In a second terminal, start the transcript server example:

```bash
npm run ws:dev
```

## End-to-end tests

Smoke tests live in `frontend/e2e/` and run against a full stack (frontend on `:3000`, backend on `:8000`).

```bash
# Requires backend running on :8000 and frontend on :3000
npm run test:e2e          # headless
npm run test:e2e:ui       # interactive Playwright UI
```

CI runs these against an ephemeral backend + frontend via `.github/workflows/ci-jobs.yml`.
Traces, screenshots, and videos are retained on failure and uploaded as artifacts.

Coverage:
- `smoke-auth.spec.ts` — landing page + NextAuth entry + onboarding + dashboard shell
- `smoke-agent.spec.ts` — bot profile form interactivity (name, persona preset, voice)
- `smoke-chat.spec.ts` — chat sidebar open + user-side send (conditional on seeded meeting)
- `smoke-sentry.spec.ts` — skipped unless `SENTRY_DSN` is set
