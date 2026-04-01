/**
 * Centralized AI prompts for TranscribeAI.
 *
 * All prompts that are sent to the AI model are defined here to:
 *  - ensure consistency across the codebase,
 *  - prevent prompt injection from transcript text, and
 *  - enforce the "never hallucinate" contract by explicitly instructing
 *    the model to use only information present in the transcript.
 *
 * IMPORTANT: Transcript text is treated as untrusted input.  It is passed
 * as a clearly delimited data block so that the model cannot be instructed
 * to ignore previous rules via the transcript content.
 */

/**
 * Generates the system prompt for meeting summarization.
 * The system message establishes strict grounding rules that are independent
 * of any user-supplied content.
 */
export const SUMMARIZATION_SYSTEM_PROMPT = `You are an AI assistant that produces concise, accurate meeting summaries.

Rules you MUST follow:
1. Only use information explicitly stated in the transcript provided.
2. Do NOT add, infer, or invent facts, decisions, or action items that are not present in the transcript.
3. Do NOT include your own opinions or external knowledge.
4. If the transcript does not contain enough information to summarize a section, state that clearly rather than guessing.
5. Never reproduce personally identifiable information (PII) unless it appears in the transcript and is necessary for accuracy.
6. Output plain text only — no markdown, no HTML.`;

/**
 * Builds the user message for summarization.
 * The transcript is wrapped in explicit delimiters so the model can
 * distinguish instruction text from untrusted transcript content.
 *
 * @param transcriptText - Raw transcript text (treated as untrusted input).
 * @returns A structured user message string.
 */
export function buildSummarizationUserPrompt(transcriptText: string): string {
  return (
    `Summarize the following meeting transcript. Limit the summary to key ` +
    `topics discussed, decisions made, and action items assigned.\n\n` +
    `--- BEGIN TRANSCRIPT ---\n` +
    `${transcriptText}\n` +
    `--- END TRANSCRIPT ---`
  );
}

/**
 * System prompt for decision extraction.
 */
export const DECISION_EXTRACTION_SYSTEM_PROMPT = `You are an AI assistant that extracts decisions from meeting transcripts.

Rules you MUST follow:
1. Only extract decisions that are explicitly stated in the transcript.
2. Do NOT infer or fabricate decisions that are not clearly expressed.
3. Return each decision as a separate line.
4. If no decisions are found, return the exact string: NO_DECISIONS_FOUND
5. Output plain text only — no markdown, no HTML, no numbering.`;

/**
 * Builds the user message for decision extraction.
 *
 * @param transcriptText - Raw transcript text (treated as untrusted input).
 */
export function buildDecisionExtractionUserPrompt(
  transcriptText: string
): string {
  return (
    `Extract all decisions from the following meeting transcript.\n\n` +
    `--- BEGIN TRANSCRIPT ---\n` +
    `${transcriptText}\n` +
    `--- END TRANSCRIPT ---`
  );
}

/**
 * System prompt for action item extraction.
 */
export const ACTION_ITEM_EXTRACTION_SYSTEM_PROMPT = `You are an AI assistant that extracts action items from meeting transcripts.

Rules you MUST follow:
1. Only extract action items that are explicitly mentioned in the transcript.
2. Do NOT infer or fabricate tasks that are not clearly assigned or agreed upon.
3. For each action item include: description, assignee (if mentioned), due date (if mentioned).
4. Format each item as: DESCRIPTION | ASSIGNEE | DUE_DATE  (use UNKNOWN for missing fields).
5. If no action items are found, return the exact string: NO_ACTION_ITEMS_FOUND
6. Output plain text only — no markdown, no HTML.`;

/**
 * Builds the user message for action item extraction.
 *
 * @param transcriptText - Raw transcript text (treated as untrusted input).
 */
export function buildActionItemExtractionUserPrompt(
  transcriptText: string
): string {
  return (
    `Extract all action items from the following meeting transcript.\n\n` +
    `--- BEGIN TRANSCRIPT ---\n` +
    `${transcriptText}\n` +
    `--- END TRANSCRIPT ---`
  );
}
