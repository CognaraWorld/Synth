/**
 * Input sanitization utilities.
 *
 * Transcript text arrives from external sources and must be treated as
 * untrusted input.  These helpers strip or escape content that could
 * cause issues when embedded in AI prompts, stored in databases, or
 * rendered in responses.
 */

/** Maximum allowed transcript length (characters). */
export const MAX_TRANSCRIPT_LENGTH = 100_000;

/** Maximum allowed title / short-string length (characters). */
export const MAX_TITLE_LENGTH = 500;

/**
 * Sanitizes transcript text received from an external transcription provider
 * or uploaded by a user.
 *
 * - Strips null bytes that can confuse downstream processing.
 * - Normalizes line endings.
 * - Enforces a maximum length to prevent denial-of-service via enormous inputs.
 *
 * Does NOT strip the content further because the full text is needed for
 * accurate summarization; instead the prompt layer uses delimiters to prevent
 * prompt injection (see src/prompts/index.ts).
 *
 * @param raw - Untrusted transcript text.
 * @returns Sanitized transcript text.
 * @throws {Error} When the input exceeds `MAX_TRANSCRIPT_LENGTH`.
 */
export function sanitizeTranscriptText(raw: string): string {
  if (typeof raw !== "string") {
    throw new Error("Transcript text must be a string.");
  }

  // Remove null bytes.
  let sanitized = raw.replace(/\0/g, "");

  // Normalize line endings to LF.
  sanitized = sanitized.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  // Enforce maximum length after normalization.
  if (sanitized.length > MAX_TRANSCRIPT_LENGTH) {
    throw new Error(
      `Transcript text exceeds the maximum allowed length of ${MAX_TRANSCRIPT_LENGTH} characters.`
    );
  }

  return sanitized;
}

/**
 * Sanitizes a short string (e.g. title, assignee name) used in metadata.
 *
 * - Strips null bytes.
 * - Trims surrounding whitespace.
 * - Enforces a maximum length.
 *
 * @param raw - Untrusted short string.
 * @returns Sanitized string.
 * @throws {Error} When the input exceeds `MAX_TITLE_LENGTH`.
 */
export function sanitizeShortString(raw: string): string {
  if (typeof raw !== "string") {
    throw new Error("Value must be a string.");
  }

  let sanitized = raw.replace(/\0/g, "").trim();

  if (sanitized.length > MAX_TITLE_LENGTH) {
    throw new Error(
      `String exceeds the maximum allowed length of ${MAX_TITLE_LENGTH} characters.`
    );
  }

  return sanitized;
}

/**
 * Validates that a URL string has an acceptable scheme (https only).
 * Audio/recording URLs must use HTTPS to protect data in transit.
 *
 * @param url - URL string to validate.
 * @throws {Error} When the URL is invalid or uses a non-HTTPS scheme.
 */
export function validateHttpsUrl(url: string): void {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`Invalid URL: "${url}".`);
  }

  if (parsed.protocol !== "https:") {
    throw new Error(
      `Audio URL must use HTTPS. Received protocol: "${parsed.protocol}".`
    );
  }
}
