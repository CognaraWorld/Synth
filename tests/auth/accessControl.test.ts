import {
  assertOwnership,
  assertJobOwnership,
  AccessDeniedError,
} from "../../src/auth/accessControl";

describe("assertOwnership", () => {
  it("does not throw when the requesting user owns the resource", () => {
    expect(() =>
      assertOwnership("user-1", "user-1", "Transcript", "transcript-abc")
    ).not.toThrow();
  });

  it("throws AccessDeniedError when the requesting user does not own the resource", () => {
    expect(() =>
      assertOwnership("user-1", "user-2", "Transcript", "transcript-abc")
    ).toThrow(AccessDeniedError);
  });

  it("includes the resource type and id in the error message", () => {
    expect(() =>
      assertOwnership("owner", "intruder", "Recording", "rec-123")
    ).toThrow(/Recording.*rec-123/);
  });

  it("AccessDeniedError has statusCode 403", () => {
    const err = new AccessDeniedError("forbidden");
    expect(err.statusCode).toBe(403);
  });
});

describe("assertJobOwnership", () => {
  it("does not throw when payload owner matches requesting user", () => {
    expect(() =>
      assertJobOwnership("user-1", "user-1", "job-xyz")
    ).not.toThrow();
  });

  it("throws AccessDeniedError when owners do not match", () => {
    expect(() =>
      assertJobOwnership("user-1", "user-2", "job-xyz")
    ).toThrow(AccessDeniedError);
  });

  it("includes the job id in the error message", () => {
    expect(() =>
      assertJobOwnership("user-a", "user-b", "job-999")
    ).toThrow(/job-999/);
  });
});
