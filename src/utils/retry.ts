/**
 * Retry and timeout utilities for job execution.
 *
 * Jobs that call external services (AI APIs, audio processors) must be
 * resilient to transient failures.  These helpers provide:
 *  - Exponential back-off retries with jitter.
 *  - Per-attempt timeouts via AbortSignal / Promise.race.
 */

/** Options for {@link withRetry}. */
export interface RetryOptions {
  /** Maximum number of attempts (first call + retries). */
  maxAttempts: number;
  /** Base delay in milliseconds for the first back-off interval. */
  baseDelayMs: number;
  /** Maximum delay cap in milliseconds. */
  maxDelayMs: number;
  /** Per-attempt timeout in milliseconds (0 = no timeout). */
  timeoutMs: number;
}

export const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxAttempts: 3,
  baseDelayMs: 500,
  maxDelayMs: 10_000,
  timeoutMs: 30_000,
};

/**
 * Wraps an async operation with retries and per-attempt timeouts.
 *
 * Uses full jitter exponential back-off:
 *   delay = random(0, min(maxDelayMs, baseDelayMs * 2^attempt))
 *
 * @param operation - Async factory; receives the attempt number (0-indexed).
 * @param options   - Retry / timeout configuration.
 * @returns The resolved value of the first successful attempt.
 * @throws The last error if all attempts are exhausted.
 */
export async function withRetry<T>(
  operation: (attempt: number) => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const opts: RetryOptions = { ...DEFAULT_RETRY_OPTIONS, ...options };

  let lastError: Error = new Error("No attempts made.");

  for (let attempt = 0; attempt < opts.maxAttempts; attempt++) {
    try {
      const result = await withTimeout(
        () => operation(attempt),
        opts.timeoutMs
      );
      return result;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      const isLastAttempt = attempt === opts.maxAttempts - 1;
      if (isLastAttempt) break;

      const delay = computeBackoffDelay(attempt, opts.baseDelayMs, opts.maxDelayMs);
      await sleep(delay);
    }
  }

  throw lastError;
}

/**
 * Wraps an async operation with a timeout.
 *
 * @param operation  - Async factory to run.
 * @param timeoutMs  - Maximum milliseconds to wait (0 = no limit).
 * @returns Resolved value of the operation.
 * @throws {Error} "Operation timed out" when the timeout elapses first.
 */
export async function withTimeout<T>(
  operation: () => Promise<T>,
  timeoutMs: number
): Promise<T> {
  if (timeoutMs <= 0) {
    return operation();
  }

  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Operation timed out after ${timeoutMs}ms.`));
    }, timeoutMs);

    operation().then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      }
    );
  });
}

/**
 * Computes an exponential back-off delay with full jitter.
 *
 * @param attempt     - Zero-indexed attempt number.
 * @param baseDelayMs - Base delay in milliseconds.
 * @param maxDelayMs  - Maximum delay cap in milliseconds.
 */
export function computeBackoffDelay(
  attempt: number,
  baseDelayMs: number,
  maxDelayMs: number
): number {
  const exponential = baseDelayMs * Math.pow(2, attempt);
  const capped = Math.min(exponential, maxDelayMs);
  return Math.random() * capped;
}

/** Promise-based sleep. */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
