import { test, expect } from "@playwright/test";

/**
 * Sentry smoke — skipped unless SENTRY_DSN is set.
 *
 * Verifies the deliberate-throw page (/sentry-test) fires a pageerror that
 * Sentry would capture in production. We don't assert against Sentry's API
 * here — just that the throw actually propagates.
 */
test.describe("Sentry smoke", () => {
  test.skip(!process.env.SENTRY_DSN, "SENTRY_DSN not set — skipping Sentry smoke");

  test("deliberate throw fires a pageerror", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto("/sentry-test");
    await page.getByRole("button", { name: /throw test error/i }).click();
    await page.waitForTimeout(500);

    expect(errors.some((e) => e.includes("Sentry E2E verification"))).toBe(true);
  });
});
