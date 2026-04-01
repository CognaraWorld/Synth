import {
  processSummarizationJob,
  SummarizationJobDeps,
  TranscriptRepository,
} from "../../src/jobs/SummarizationJob";
import {
  SummarizationService,
  StubAIProvider,
} from "../../src/services/SummarizationService";
import { InMemoryIdempotencyStore } from "../../src/utils/idempotency";
import { AccessDeniedError } from "../../src/auth/accessControl";

const STUB_TRANSCRIPT_TEXT =
  "Alice: We decided to ship by Friday.\nBob: I will handle deployment.";

function makeTranscriptRepo(
  text = STUB_TRANSCRIPT_TEXT
): TranscriptRepository {
  return {
    getTranscriptText: jest.fn().mockResolvedValue(text),
  };
}

function makeDeps(
  overrides: Partial<SummarizationJobDeps> = {}
): SummarizationJobDeps {
  return {
    summarizationService: new SummarizationService({
      aiProvider: new StubAIProvider(),
    }),
    transcriptRepository: makeTranscriptRepo(),
    idempotencyStore: new InMemoryIdempotencyStore(),
    retryOptions: { maxAttempts: 1, baseDelayMs: 0, maxDelayMs: 0, timeoutMs: 0 },
    ...overrides,
  };
}

const VALID_PAYLOAD = {
  jobId: "sum-job-1",
  transcriptId: "transcript-1",
  ownerId: "user-1",
};

describe("processSummarizationJob", () => {
  it("completes successfully and returns a summarization result", async () => {
    const deps = makeDeps();
    const result = await processSummarizationJob(
      VALID_PAYLOAD,
      "user-1",
      deps
    );
    expect(result.skipped).toBe(false);
    expect(result.result?.summary).toBeDefined();
    expect(result.result?.summary.transcriptId).toBe("transcript-1");
  });

  it("marks the job as completed in the idempotency store", async () => {
    const deps = makeDeps();
    await processSummarizationJob(VALID_PAYLOAD, "user-1", deps);
    const record = await deps.idempotencyStore.get("sum-job-1");
    expect(record?.status).toBe("completed");
  });

  it("skips a job that was already completed (idempotency)", async () => {
    const deps = makeDeps();
    await processSummarizationJob(VALID_PAYLOAD, "user-1", deps);
    const second = await processSummarizationJob(VALID_PAYLOAD, "user-1", deps);
    expect(second.skipped).toBe(true);
    expect(second.result).toBeUndefined();
  });

  it("throws AccessDeniedError when the requesting user is not the owner", async () => {
    const deps = makeDeps();
    await expect(
      processSummarizationJob(VALID_PAYLOAD, "intruder", deps)
    ).rejects.toThrow(AccessDeniedError);
  });

  it("marks the job as failed when the AI provider throws", async () => {
    const failingAI = {
      chat: jest.fn().mockRejectedValue(new Error("AI provider down")),
    };
    const deps = makeDeps({
      summarizationService: new SummarizationService({ aiProvider: failingAI }),
    });

    await expect(
      processSummarizationJob(VALID_PAYLOAD, "user-1", deps)
    ).rejects.toThrow("AI provider down");

    const record = await deps.idempotencyStore.get("sum-job-1");
    expect(record?.status).toBe("failed");
    expect(record?.error).toContain("AI provider down");
  });

  it("throws when an identical job is already processing", async () => {
    const deps = makeDeps();
    await deps.idempotencyStore.set({
      jobId: "sum-job-1",
      status: "processing",
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    await expect(
      processSummarizationJob(VALID_PAYLOAD, "user-1", deps)
    ).rejects.toThrow(/already being processed/);
  });
});
