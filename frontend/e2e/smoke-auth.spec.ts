import { test, expect } from "@playwright/test";

/**
 * Auth entry smoke.
 *
 * Reality check: Synth uses NextAuth with Google OAuth + email magic links.
 * There is no `/register` or `/login` page with password fields — the landing
 * page sends users to `/api/auth/signin` (NextAuth default UI) or `/onboarding`
 * (bot setup wizard). A true end-to-end register→login→dashboard flow would
 * require OAuth mocking or a credentials provider, neither of which exists.
 *
 * This spec verifies the reachable entry points render correctly.
 */
test.describe("Auth entry smoke", () => {
  test("landing page shows sign-in + create-account CTAs", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: /synth/i, level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: /sign in/i }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: /get started/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /create account/i })).toBeVisible();
  });

  test("sign-in link routes to NextAuth signin page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /get started/i }).click();

    // NextAuth default signin lives at /api/auth/signin; with no providers
    // configured it falls through to /onboarding via pages.signIn.
    await expect(page).toHaveURL(/\/(api\/auth\/signin|onboarding)/, { timeout: 10_000 });
  });

  test("create-account link routes to onboarding step 1", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /create account/i }).click();

    await expect(page).toHaveURL(/\/onboarding/);
    await expect(page.getByRole("heading", { name: /set up your bot/i })).toBeVisible();
    await expect(page.getByLabel(/bot name/i)).toBeVisible();
  });

  test("dashboard renders without sample-data banner", async ({ page }) => {
    // DashboardLayout tolerates missing session (demo mode) and still renders,
    // so we can smoke-test the page shell without authenticating.
    await page.goto("/dashboard");

    await expect(page.getByText(/sample data|fake data|mock data/i)).toHaveCount(0);
    await expect(page.getByRole("heading").first()).toBeVisible();
  });
});
