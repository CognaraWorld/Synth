import {
  SummarizationService,
  StubAIProvider,
  AIProvider,
} from "../../src/services/SummarizationService";

describe("SummarizationService", () => {
  const aiProvider = new StubAIProvider();
  const service = new SummarizationService({ aiProvider });

  it("returns a Summary with the correct transcriptId and ownerId", async () => {
    const { summary } = await service.summarize(
      "transcript-1",
      "user-1",
      "Alice: We agreed to ship by Friday.\nBob: I will handle the deployment."
    );
    expect(summary.transcriptId).toBe("transcript-1");
    expect(summary.ownerId).toBe("user-1");
  });

  it("returns a Summary with non-empty text", async () => {
    const { summary } = await service.summarize(
      "transcript-1",
      "user-1",
      "Discussion about Q3 targets."
    );
    expect(summary.text.length).toBeGreaterThan(0);
  });

  it("assigns unique ids to summaries across calls", async () => {
    const r1 = await service.summarize("t-1", "u-1", "Meeting text.");
    const r2 = await service.summarize("t-1", "u-1", "Meeting text.");
    expect(r1.summary.id).not.toBe(r2.summary.id);
  });

  it("returns empty decisions when AI responds NO_DECISIONS_FOUND", async () => {
    const noDecisionProvider: AIProvider = {
      chat: jest.fn().mockResolvedValue("NO_DECISIONS_FOUND"),
    };
    const s = new SummarizationService({ aiProvider: noDecisionProvider });
    const { decisions } = await s.summarize("t-1", "u-1", "Some transcript.");
    expect(decisions).toHaveLength(0);
  });

  it("returns empty action items when AI responds NO_ACTION_ITEMS_FOUND", async () => {
    const noItemsProvider: AIProvider = {
      chat: jest.fn().mockResolvedValue("NO_ACTION_ITEMS_FOUND"),
    };
    const s = new SummarizationService({ aiProvider: noItemsProvider });
    const { actionItems } = await s.summarize("t-1", "u-1", "Some transcript.");
    expect(actionItems).toHaveLength(0);
  });

  it("parses multiple decisions from newline-separated AI output", async () => {
    const multiDecisionProvider: AIProvider = {
      chat: jest
        .fn()
        .mockResolvedValueOnce("Stub summary.")
        .mockResolvedValueOnce("Ship by Friday\nHire a contractor")
        .mockResolvedValueOnce("NO_ACTION_ITEMS_FOUND"),
    };
    const s = new SummarizationService({ aiProvider: multiDecisionProvider });
    const { decisions } = await s.summarize("t-1", "u-1", "Transcript.");
    expect(decisions).toHaveLength(2);
    expect(decisions[0].text).toBe("Ship by Friday");
    expect(decisions[1].text).toBe("Hire a contractor");
  });

  it("parses action items with assignee and due date", async () => {
    const actionProvider: AIProvider = {
      chat: jest
        .fn()
        .mockResolvedValueOnce("Stub summary.")
        .mockResolvedValueOnce("NO_DECISIONS_FOUND")
        .mockResolvedValueOnce("Deploy to prod | Alice | 2025-06-01"),
    };
    const s = new SummarizationService({ aiProvider: actionProvider });
    const { actionItems } = await s.summarize("t-1", "u-1", "Transcript.");
    expect(actionItems).toHaveLength(1);
    expect(actionItems[0].description).toBe("Deploy to prod");
    expect(actionItems[0].assignee).toBe("Alice");
    expect(actionItems[0].dueDate).toBeInstanceOf(Date);
  });

  it("throws when the transcript exceeds the maximum length", async () => {
    const oversized = "a".repeat(100_001);
    await expect(
      service.summarize("t-1", "u-1", oversized)
    ).rejects.toThrow(/exceeds the maximum allowed length/);
  });
});
