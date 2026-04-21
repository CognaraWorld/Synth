"use client";

import { notFound } from "next/navigation";

// REMOVE BEFORE PRODUCTION LAUNCH.
// This page deliberately throws to verify Sentry wiring. It has no auth gate
// and no business logic; keeping it in prod would let anyone spam Sentry.
// Belt-and-braces: the 404 guard below makes it unreachable in production
// even if someone forgets to delete the file.
export default function SentryTestPage() {
  if (process.env.NEXT_PUBLIC_ENVIRONMENT === "production") {
    notFound();
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <button
        className="rounded-2xl border border-destructive bg-destructive/10 px-6 py-3 text-sm font-medium text-destructive"
        onClick={() => {
          throw new Error("Sentry E2E verification — " + new Date().toISOString());
        }}
      >
        Throw test error
      </button>
    </main>
  );
}
