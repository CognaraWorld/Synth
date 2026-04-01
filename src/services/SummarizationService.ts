/**
 * SummarizationService
 *
 * Generates summaries, decisions, and action items from a transcript by
 * sending centralized, grounded prompts to an AI model.
 *
 * Key contract: the model is ONLY allowed to use information from the
 * transcript.  This is enforced by the prompts defined in src/prompts/index.ts.
 */

import { Summary, Decision, ActionItem } from "../models/index.js";
import {
  SUMMARIZATION_SYSTEM_PROMPT,
  buildSummarizationUserPrompt,
  DECISION_EXTRACTION_SYSTEM_PROMPT,
  buildDecisionExtractionUserPrompt,
  ACTION_ITEM_EXTRACTION_SYSTEM_PROMPT,
  buildActionItemExtractionUserPrompt,
} from "../prompts/index.js";
import { sanitizeTranscriptText } from "../utils/sanitize.js";
import { v4 as uuidv4 } from "uuid";

export interface AIProvider {
  /**
   * Sends a system + user message pair to the AI model and returns the
   * model's text response.
   */
  chat(systemPrompt: string, userPrompt: string): Promise<string>;
}

/**
 * Stub implementation used in tests and local development.
 */
export class StubAIProvider implements AIProvider {
  async chat(_systemPrompt: string, userPrompt: string): Promise<string> {
    // Return deterministic stub output so tests are predictable.
    if (userPrompt.includes("--- BEGIN TRANSCRIPT ---")) {
      return "Stub summary: meeting discussed project milestones.";
    }
    return "NO_DECISIONS_FOUND";
  }
}

export interface SummarizationServiceDeps {
  aiProvider: AIProvider;
}

export interface SummarizationResult {
  summary: Summary;
  decisions: Decision[];
  actionItems: ActionItem[];
}

export class SummarizationService {
  private readonly aiProvider: AIProvider;

  constructor(deps: SummarizationServiceDeps) {
    this.aiProvider = deps.aiProvider;
  }

  /**
   * Summarizes a transcript and extracts decisions and action items.
   *
   * The transcript text is sanitized before being embedded in prompts to
   * prevent prompt injection attacks.
   *
   * @param transcriptId   - ID of the source transcript.
   * @param ownerId        - ID of the user who owns the transcript.
   * @param transcriptText - Raw transcript text (treated as untrusted input).
   */
  async summarize(
    transcriptId: string,
    ownerId: string,
    transcriptText: string
  ): Promise<SummarizationResult> {
    // Re-sanitize even if already sanitized at ingestion time.
    const safeText = sanitizeTranscriptText(transcriptText);

    const [summaryText, decisionsRaw, actionItemsRaw] = await Promise.all([
      this.aiProvider.chat(
        SUMMARIZATION_SYSTEM_PROMPT,
        buildSummarizationUserPrompt(safeText)
      ),
      this.aiProvider.chat(
        DECISION_EXTRACTION_SYSTEM_PROMPT,
        buildDecisionExtractionUserPrompt(safeText)
      ),
      this.aiProvider.chat(
        ACTION_ITEM_EXTRACTION_SYSTEM_PROMPT,
        buildActionItemExtractionUserPrompt(safeText)
      ),
    ]);

    const now = new Date();

    const summary: Summary = {
      id: uuidv4(),
      transcriptId,
      ownerId,
      text: summaryText.trim(),
      createdAt: now,
      updatedAt: now,
    };

    const decisions: Decision[] = this.parseDecisions(
      decisionsRaw,
      transcriptId,
      ownerId,
      now
    );

    const actionItems: ActionItem[] = this.parseActionItems(
      actionItemsRaw,
      transcriptId,
      ownerId,
      now
    );

    return { summary, decisions, actionItems };
  }

  private parseDecisions(
    raw: string,
    transcriptId: string,
    ownerId: string,
    now: Date
  ): Decision[] {
    const trimmed = raw.trim();
    if (trimmed === "NO_DECISIONS_FOUND" || trimmed === "") {
      return [];
    }

    return trimmed
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line) => ({
        id: uuidv4(),
        transcriptId,
        ownerId,
        text: line,
        createdAt: now,
        updatedAt: now,
      }));
  }

  private parseActionItems(
    raw: string,
    transcriptId: string,
    ownerId: string,
    now: Date
  ): ActionItem[] {
    const trimmed = raw.trim();
    if (trimmed === "NO_ACTION_ITEMS_FOUND" || trimmed === "") {
      return [];
    }

    return trimmed
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line) => {
        const parts = line.split("|").map((p) => p.trim());
        const description = parts[0] ?? line;
        const assignee =
          parts[1] && parts[1] !== "UNKNOWN" ? parts[1] : undefined;
        const dueDateStr =
          parts[2] && parts[2] !== "UNKNOWN" ? parts[2] : undefined;
        const dueDate = dueDateStr ? new Date(dueDateStr) : undefined;

        return {
          id: uuidv4(),
          transcriptId,
          ownerId,
          description,
          assignee,
          dueDate: dueDate && !isNaN(dueDate.getTime()) ? dueDate : undefined,
          createdAt: now,
          updatedAt: now,
        };
      });
  }
}
