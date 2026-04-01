/**
 * Data models for TranscribeAI.
 *
 * These types represent the core domain objects: recordings, transcripts,
 * summaries, decisions, and action items.
 */

export type JobStatus = "pending" | "processing" | "completed" | "failed";

export interface Recording {
  id: string;
  ownerId: string;
  title: string;
  audioUrl: string;
  durationSeconds: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface Transcript {
  id: string;
  recordingId: string;
  ownerId: string;
  /** Raw transcript text — treat as untrusted user-supplied input. */
  text: string;
  language: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Summary {
  id: string;
  transcriptId: string;
  ownerId: string;
  /** AI-generated summary grounded solely in the transcript text. */
  text: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface Decision {
  id: string;
  transcriptId: string;
  ownerId: string;
  /** Decision extracted verbatim or closely paraphrased from transcript. */
  text: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface ActionItem {
  id: string;
  transcriptId: string;
  ownerId: string;
  /** Action item extracted verbatim or closely paraphrased from transcript. */
  description: string;
  assignee?: string;
  dueDate?: Date;
  createdAt: Date;
  updatedAt: Date;
}

export interface TranscriptionJobPayload {
  jobId: string;
  recordingId: string;
  ownerId: string;
  audioUrl: string;
}

export interface SummarizationJobPayload {
  jobId: string;
  transcriptId: string;
  ownerId: string;
}

export interface JobRecord {
  jobId: string;
  status: JobStatus;
  error?: string;
  createdAt: Date;
  updatedAt: Date;
}
