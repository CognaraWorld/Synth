/**
 * SummarizationJob
 *
 * Processes a single summarization job with:
 *  - Idempotency  — skips jobs that already completed successfully.
 *  - Retries      — retries on transient failures with exponential back-off.
 *  - Timeouts     — each attempt is bounded to prevent indefinite hangs.
 *  - Auth check   — verifies the job payload owner before executing.
 */

import { SummarizationJobPayload } from "../models/index.js";
import {
  SummarizationService,
  SummarizationResult,
} from "../services/SummarizationService.js";
import { withRetry, RetryOptions } from "../utils/retry.js";
import {
  IdempotencyStore,
  isJobAlreadyCompleted,
  markJobProcessing,
  markJobCompleted,
  markJobFailed,
} from "../utils/idempotency.js";
import { assertJobOwnership } from "../auth/accessControl.js";

export interface TranscriptRepository {
  /** Fetches the transcript text by its ID. */
  getTranscriptText(transcriptId: string, ownerId: string): Promise<string>;
}

export interface SummarizationJobDeps {
  summarizationService: SummarizationService;
  transcriptRepository: TranscriptRepository;
  idempotencyStore: IdempotencyStore;
  retryOptions?: Partial<RetryOptions>;
}

export interface SummarizationJobResult {
  skipped: boolean;
  result?: SummarizationResult;
}

/**
 * Processes a summarization job.
 *
 * @param payload          - Job payload containing transcriptId and ownerId.
 * @param requestingUserId - User ID submitting or processing the job.
 * @param deps             - Injected dependencies.
 */
export async function processSummarizationJob(
  payload: SummarizationJobPayload,
  requestingUserId: string,
  deps: SummarizationJobDeps
): Promise<SummarizationJobResult> {
  const { jobId, transcriptId, ownerId } = payload;
  const {
    summarizationService,
    transcriptRepository,
    idempotencyStore,
    retryOptions,
  } = deps;

  // 1. Auth check — ensure the submitting user owns this job.
  assertJobOwnership(ownerId, requestingUserId, jobId);

  // 2. Idempotency check — skip if already successfully completed.
  if (await isJobAlreadyCompleted(idempotencyStore, jobId)) {
    return { skipped: true };
  }

  // 3. Mark as processing (prevents duplicate concurrent execution).
  await markJobProcessing(idempotencyStore, jobId);

  try {
    // 4. Execute with retries and per-attempt timeout.
    const result = await withRetry(
      async () => {
        // Fetch transcript text inside the retry loop so that if the
        // fetch itself is transient, it is also retried.
        const transcriptText = await transcriptRepository.getTranscriptText(
          transcriptId,
          ownerId
        );
        return summarizationService.summarize(transcriptId, ownerId, transcriptText);
      },
      retryOptions
    );

    // 5. Mark completed.
    await markJobCompleted(idempotencyStore, jobId);

    return { skipped: false, result };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await markJobFailed(idempotencyStore, jobId, message);
    throw err;
  }
}
