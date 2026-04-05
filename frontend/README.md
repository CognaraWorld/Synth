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
