/**
 * TranscriptionJob
 *
 * Processes a single transcription job with:
 *  - Idempotency  — skips jobs that already completed successfully.
 *  - Retries      — retries on transient failures with exponential back-off.
 *  - Timeouts     — each attempt is bounded to prevent indefinite hangs.
 *  - Auth check   — verifies the job payload owner before executing.
 */

import { TranscriptionJobPayload, Transcript } from "../models/index.js";
import { TranscriptionService } from "../services/TranscriptionService.js";
import { withRetry, RetryOptions } from "../utils/retry.js";
import {
  IdempotencyStore,
  isJobAlreadyCompleted,
  markJobProcessing,
  markJobCompleted,
  markJobFailed,
} from "../utils/idempotency.js";
import { assertJobOwnership } from "../auth/accessControl.js";

export interface TranscriptionJobDeps {
  transcriptionService: TranscriptionService;
  idempotencyStore: IdempotencyStore;
  retryOptions?: Partial<RetryOptions>;
}

export interface TranscriptionJobResult {
  skipped: boolean;
  transcript?: Transcript;
}

/**
 * Processes a transcription job.
 *
 * @param payload          - Job payload containing recordingId, audioUrl, ownerId.
 * @param requestingUserId - User ID submitting or processing the job.
 * @param deps             - Injected dependencies.
 */
export async function processTranscriptionJob(
  payload: TranscriptionJobPayload,
  requestingUserId: string,
  deps: TranscriptionJobDeps
): Promise<TranscriptionJobResult> {
  const { jobId, recordingId, ownerId, audioUrl } = payload;
  const { transcriptionService, idempotencyStore, retryOptions } = deps;

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
    const transcript = await withRetry(
      () =>
        transcriptionService.transcribe(
          recordingId,
          ownerId,
          audioUrl
        ),
      retryOptions
    );

    // 5. Mark completed.
    await markJobCompleted(idempotencyStore, jobId);

    return { skipped: false, transcript };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await markJobFailed(idempotencyStore, jobId, message);
    throw err;
  }
}
