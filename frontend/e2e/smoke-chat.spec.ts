import { test, expect } from "@playwright/test";

/**
 * Chat sidebar smoke.
 *
 * The chat sidebar only opens when a meeting exists. Triggers are:
 *   - Past meeting card → "Ask about this meeting" button
 *   - Live meeting → bot-control-panel → "Chat" button
 * Both call openChat(meetingId) which mounts <ChatSidebar> with the meeting ID.
 *
 * The sidebar exposes an <Input> with placeholder "Ask Cognara..." (or
 * "Compare decisions, ask about trends..." when crossMeeting=true) and a
 * "Send" button. Hitting Enter or clicking Send calls sendMessage(input).
 *
 * This smoke is conditional: if the seeded database has no meetings, it skips.
 * That's by design — beta smoke should not require specific test fixtures.
 */
test.describe("Chat sidebar smoke", () => {
  test("chat sidebar opens and input accepts a message", async ({ page }) => {
    await page.goto("/dashboard/meetings");

    await expect(page.getByRole("heading", { name: /your meetings/i })).toBeVisible({
      timeout: 10_000,
    });

    // Prefer past-meeting trigger; fall back to live-meeting Chat button.
    const askButton = page.getByRole("button", { name: /ask about this meeting/i }).first();
    const chatButton = page.getByRole("button", { name: /^chat$/i }).first();

    const hasAsk = (await askButton.count()) > 0;
    const hasChat = (await chatButton.count()) > 0;

    if (!hasAsk && !hasChat) {
      test.skip(true, "No meetings seeded — chat trigger unreachable");
      return;
    }

    if (hasAsk) {
      await askButton.click();
    } else {
      await chatButton.click();
    }

    // Sidebar title confirms the sheet is open.
    await expect(page.getByRole("heading", { name: /chat with cognara/i })).toBeVisible({
      timeout: 5_000,
    });

    const chatInput = page.getByPlaceholder(/ask cognara/i);
    await expect(chatInput).toBeVisible();

    const testMessage = `e2e smoke ${Date.now()}`;
    await chatInput.fill(testMessage);
    await expect(chatInput).toHaveValue(testMessage);

    // Send button exists and is enabled once input has content.
    const sendButton = page.getByRole("button", { name: /^send$/i });
    await expect(sendButton).toBeEnabled();

    await chatInput.press("Enter");

    // User's own message bubble renders verbatim. Assistant reply depends on
    // backend availability, so we only assert the user-side echo here.
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 5_000 });
  });
});
