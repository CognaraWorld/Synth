import {
  processTranscriptionJob,
  TranscriptionJobDeps,
} from "../../src/jobs/TranscriptionJob";
import {
  TranscriptionService,
  StubTranscriptionProvider,
} from "../../src/services/TranscriptionService";
import { InMemoryIdempotencyStore } from "../../src/utils/idempotency";
import { AccessDeniedError } from "../../src/auth/accessControl";

function makeDeps(
  overrides: Partial<TranscriptionJobDeps> = {}
): TranscriptionJobDeps {
  return {
    transcriptionService: new TranscriptionService({
      provider: new StubTranscriptionProvider(),
    }),
    idempotencyStore: new InMemoryIdempotencyStore(),
    retryOptions: { maxAttempts: 1, baseDelayMs: 0, maxDelayMs: 0, timeoutMs: 0 },
    ...overrides,
  };
}

const VALID_PAYLOAD = {
  jobId: "job-1",
  recordingId: "rec-1",
  ownerId: "user-1",
  audioUrl: "https://example.com/audio.mp3",
};

describe("processTranscriptionJob", () => {
  it("completes successfully and returns a transcript", async () => {
    const deps = makeDeps();
    const result = await processTranscriptionJob(VALID_PAYLOAD, "user-1", deps);
    expect(result.skipped).toBe(false);
    expect(result.transcript).toBeDefined();
    expect(result.transcript?.recordingId).toBe("rec-1");
  });

  it("marks the job as completed in the idempotency store", async () => {
    const deps = makeDeps();
    await processTranscriptionJob(VALID_PAYLOAD, "user-1", deps);
    const record = await deps.idempotencyStore.get("job-1");
    expect(record?.status).toBe("completed");
  });

  it("skips a job that was already completed (idempotency)", async () => {
    const deps = makeDeps();
    await processTranscriptionJob(VALID_PAYLOAD, "user-1", deps);
    const secondResult = await processTranscriptionJob(
      VALID_PAYLOAD,
      "user-1",
      deps
    );
    expect(secondResult.skipped).toBe(true);
    expect(secondResult.transcript).toBeUndefined();
  });

  it("throws AccessDeniedError when the requesting user is not the owner", async () => {
    const deps = makeDeps();
    await expect(
      processTranscriptionJob(VALID_PAYLOAD, "intruder", deps)
    ).rejects.toThrow(AccessDeniedError);
  });

  it("marks the job as failed when the transcription service throws", async () => {
    const failingProvider = {
      transcribeAudio: jest
        .fn()
        .mockRejectedValue(new Error("provider error")),
    };
    const deps = makeDeps({
      transcriptionService: new TranscriptionService({ provider: failingProvider }),
    });

    await expect(
      processTranscriptionJob(VALID_PAYLOAD, "user-1", deps)
    ).rejects.toThrow("provider error");

    const record = await deps.idempotencyStore.get("job-1");
    expect(record?.status).toBe("failed");
    expect(record?.error).toContain("provider error");
  });

  it("throws when an identical job is already processing", async () => {
    const deps = makeDeps();
    // Manually place the job in processing state.
    await deps.idempotencyStore.set({
      jobId: "job-1",
      status: "processing",
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    await expect(
      processTranscriptionJob(VALID_PAYLOAD, "user-1", deps)
    ).rejects.toThrow(/already being processed/);
  });
});
