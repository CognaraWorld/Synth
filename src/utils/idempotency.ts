/**
 * In-memory idempotency store for jobs.
 *
 * In production this would be backed by a persistent store (Redis, a database
 * table, etc.).  The interface is kept generic so that a real implementation
 * can be swapped in without changing job logic.
 */

import { JobRecord, JobStatus } from "../models/index.js";

export interface IdempotencyStore {
  /** Returns the existing record for jobId, or undefined if not found. */
  get(jobId: string): Promise<JobRecord | undefined>;
  /** Persists or updates a job record. */
  set(record: JobRecord): Promise<void>;
}

/**
 * Simple in-memory implementation suitable for testing and single-process
 * deployments.  Not safe for multi-process / distributed use.
 */
export class InMemoryIdempotencyStore implements IdempotencyStore {
  private readonly store = new Map<string, JobRecord>();

  async get(jobId: string): Promise<JobRecord | undefined> {
    return this.store.get(jobId);
  }

  async set(record: JobRecord): Promise<void> {
    this.store.set(record.jobId, { ...record });
  }
}

/**
 * Checks whether a job has already been completed successfully.
 * Returns `true` if the job should be skipped (idempotent deduplication).
 */
export async function isJobAlreadyCompleted(
  store: IdempotencyStore,
  jobId: string
): Promise<boolean> {
  const record = await store.get(jobId);
  return record?.status === "completed";
}

/**
 * Marks a job as "processing" in the idempotency store.
 * Throws if the job is already in "processing" state (duplicate in-flight).
 */
export async function markJobProcessing(
  store: IdempotencyStore,
  jobId: string
): Promise<void> {
  const existing = await store.get(jobId);
  if (existing?.status === "processing") {
    throw new Error(`Job "${jobId}" is already being processed.`);
  }
  await store.set({
    jobId,
    status: "processing" as JobStatus,
    createdAt: existing?.createdAt ?? new Date(),
    updatedAt: new Date(),
  });
}

/** Marks a job as completed. */
export async function markJobCompleted(
  store: IdempotencyStore,
  jobId: string
): Promise<void> {
  const existing = await store.get(jobId);
  await store.set({
    jobId,
    status: "completed" as JobStatus,
    createdAt: existing?.createdAt ?? new Date(),
    updatedAt: new Date(),
  });
}

/** Marks a job as failed with an error message. */
export async function markJobFailed(
  store: IdempotencyStore,
  jobId: string,
  error: string
): Promise<void> {
  const existing = await store.get(jobId);
  await store.set({
    jobId,
    status: "failed" as JobStatus,
    error,
    createdAt: existing?.createdAt ?? new Date(),
    updatedAt: new Date(),
  });
}
