/**
 * Access control utilities.
 *
 * Private meeting data (recordings, transcripts, summaries, decisions, action
 * items) is scoped to its owner.  Every read/write operation must verify that
 * the requesting user owns the resource.
 */

/**
 * Verifies that `requestingUserId` matches the resource's `ownerId`.
 *
 * @param ownerId          - The user ID that owns the resource.
 * @param requestingUserId - The user ID making the request.
 * @param resourceType     - Human-readable resource name for error messages.
 * @param resourceId       - Resource identifier for error messages.
 * @throws {AccessDeniedError} When the requesting user does not own the resource.
 */
export function assertOwnership(
  ownerId: string,
  requestingUserId: string,
  resourceType: string,
  resourceId: string
): void {
  if (ownerId !== requestingUserId) {
    throw new AccessDeniedError(
      `User "${requestingUserId}" does not have access to ${resourceType} "${resourceId}".`
    );
  }
}

/**
 * Thrown when a user attempts to access a resource they do not own.
 */
export class AccessDeniedError extends Error {
  readonly statusCode = 403;

  constructor(message: string) {
    super(message);
    this.name = "AccessDeniedError";
    // Maintains proper prototype chain in ES5 compiled output.
    Object.setPrototypeOf(this, AccessDeniedError.prototype);
  }
}

/**
 * Verifies that a job's payload owner matches the requesting user.
 * Used by job processors before executing sensitive operations.
 *
 * @param payloadOwnerId   - Owner stored in the job payload.
 * @param requestingUserId - User who submitted or is processing the job.
 */
export function assertJobOwnership(
  payloadOwnerId: string,
  requestingUserId: string,
  jobId: string
): void {
  if (payloadOwnerId !== requestingUserId) {
    throw new AccessDeniedError(
      `User "${requestingUserId}" is not authorized to process job "${jobId}".`
    );
  }
}
