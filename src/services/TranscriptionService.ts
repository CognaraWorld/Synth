/**
 * TranscriptionService
 *
 * Handles interaction with the external transcription provider.
 * In production, replace `transcribeAudio` with a real API call
 * (e.g., OpenAI Whisper, AssemblyAI, Deepgram, etc.).
 *
 * This module is intentionally thin; all retry / timeout / idempotency logic
 * lives in TranscriptionJob.
 */

import { Transcript } from "../models/index.js";
import { sanitizeTranscriptText, validateHttpsUrl } from "../utils/sanitize.js";
import { v4 as uuidv4 } from "uuid";

export interface TranscriptionProvider {
  /**
   * Calls the external transcription API and returns the raw transcript text.
   *
   * @param audioUrl - HTTPS URL of the audio file to transcribe.
   * @param language - BCP-47 language code (e.g. "en-US").
   */
  transcribeAudio(audioUrl: string, language?: string): Promise<string>;
}

/**
 * Stub implementation used in tests and local development.
 * Replace with a real provider in production.
 */
export class StubTranscriptionProvider implements TranscriptionProvider {
  async transcribeAudio(audioUrl: string): Promise<string> {
    // Validate URL even in stub mode.
    validateHttpsUrl(audioUrl);
    return `[Stub transcript for audio at ${audioUrl}]`;
  }
}

export interface TranscriptionServiceDeps {
  provider: TranscriptionProvider;
}

export class TranscriptionService {
  private readonly provider: TranscriptionProvider;

  constructor(deps: TranscriptionServiceDeps) {
    this.provider = deps.provider;
  }

  /**
   * Transcribes a recording and returns a sanitized Transcript object.
   *
   * @param recordingId - ID of the recording being transcribed.
   * @param ownerId     - ID of the user who owns the recording.
   * @param audioUrl    - HTTPS URL of the audio file.
   * @param language    - BCP-47 language code for transcription.
   */
  async transcribe(
    recordingId: string,
    ownerId: string,
    audioUrl: string,
    language = "en-US"
  ): Promise<Transcript> {
    // Validate the URL before touching external services.
    validateHttpsUrl(audioUrl);

    // Call the external provider.
    const rawText = await this.provider.transcribeAudio(audioUrl, language);

    // Sanitize the provider's output — treat it as untrusted input.
    const sanitizedText = sanitizeTranscriptText(rawText);

    const now = new Date();
    return {
      id: uuidv4(),
      recordingId,
      ownerId,
      text: sanitizedText,
      language,
      createdAt: now,
      updatedAt: now,
    };
  }
}
