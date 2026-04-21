"use client";

// REMOVE BEFORE PRODUCTION LAUNCH.
// This page deliberately throws to verify Sentry wiring. It has no auth gate
// and no business logic; keeping it in prod would let anyone spam Sentry.
export default function SentryTestPage() {
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
