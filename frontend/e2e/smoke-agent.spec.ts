import { test, expect } from "@playwright/test";

/**
 * Agent (bot profile) creation smoke.
 *
 * Synth has a single bot profile per user (not a list of agents). The flow is:
 *   /dashboard/bot → edit "Bot name (wake word)" + persona/voice → Save changes
 * The save button flips to "Saved!" for 2s on success.
 *
 * DashboardLayout runs in demo mode when no session exists, so the page shell
 * renders unauthenticated. The PUT to /api/bot-profile may 401 without a
 * session; in that case "Save changes" will stay as "Saving..." / not flip to
 * "Saved!". The smoke asserts form interactivity, not persistence.
 */
test.describe("Bot profile smoke", () => {
  test("bot name field is editable and save button is reachable", async ({ page }) => {
    await page.goto("/dashboard/bot");

    const nameInput = page.getByLabel(/bot name/i);
    await expect(nameInput).toBeVisible({ timeout: 10_000 });

    const agentName = `Nova-${Date.now()}`;
    await nameInput.fill(agentName);
    await expect(nameInput).toHaveValue(agentName);

    const saveButton = page.getByRole("button", { name: /save changes|saving|saved/i });
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeEnabled();
  });

  test("persona preset buttons apply to textarea", async ({ page }) => {
    await page.goto("/dashboard/bot");

    const personaTextarea = page.getByPlaceholder(/describe how your bot should communicate/i);
    await expect(personaTextarea).toBeVisible({ timeout: 10_000 });

    // personaPresets includes "general", "strategist", etc. Click the first
    // visible preset button and confirm the textarea updates.
    const presetButton = page
      .getByRole("button", { name: /strategist|analyst|challenger|facilitator|general/i })
      .first();
    await presetButton.click();

    await expect(personaTextarea).not.toHaveValue("");
  });

  test("voice radio group toggles between male and female", async ({ page }) => {
    await page.goto("/dashboard/bot");

    // Voice options render as Radix RadioGroupItem with aria-label set to the
    // option label ("Male" | "Female"); select by accessible name, never by
    // position — a new fieldset above voice would silently shift indices.
    const maleRadio = page.getByRole("radio", { name: /^male$/i });
    const femaleRadio = page.getByRole("radio", { name: /^female$/i });

    await expect(maleRadio).toBeVisible({ timeout: 10_000 });
    await expect(femaleRadio).toBeVisible();

    await maleRadio.click();
    await expect(maleRadio).toBeChecked();
    await expect(femaleRadio).not.toBeChecked();

    await femaleRadio.click();
    await expect(femaleRadio).toBeChecked();
    await expect(maleRadio).not.toBeChecked();
  });
});
