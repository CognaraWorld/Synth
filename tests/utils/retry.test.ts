import { withRetry, withTimeout, computeBackoffDelay } from "../../src/utils/retry";

describe("withTimeout", () => {
  it("resolves when the operation completes before the timeout", async () => {
    const result = await withTimeout(() => Promise.resolve(42), 1000);
    expect(result).toBe(42);
  });

  it("rejects when the operation exceeds the timeout", async () => {
    await expect(
      withTimeout(
        () => new Promise((resolve) => setTimeout(resolve, 200)),
        50
      )
    ).rejects.toThrow(/timed out/);
  });

  it("does not apply a timeout when timeoutMs is 0", async () => {
    const result = await withTimeout(() => Promise.resolve("ok"), 0);
    expect(result).toBe("ok");
  });
});

describe("withRetry", () => {
  it("returns the result immediately on first success", async () => {
    const op = jest.fn().mockResolvedValue("success");
    const result = await withRetry(op, {
      maxAttempts: 3,
      baseDelayMs: 0,
      maxDelayMs: 0,
      timeoutMs: 0,
    });
    expect(result).toBe("success");
    expect(op).toHaveBeenCalledTimes(1);
  });

  it("retries on failure and succeeds on second attempt", async () => {
    const op = jest
      .fn()
      .mockRejectedValueOnce(new Error("transient"))
      .mockResolvedValueOnce("recovered");

    const result = await withRetry(op, {
      maxAttempts: 3,
      baseDelayMs: 0,
      maxDelayMs: 0,
      timeoutMs: 0,
    });
    expect(result).toBe("recovered");
    expect(op).toHaveBeenCalledTimes(2);
  });

  it("throws the last error after exhausting all attempts", async () => {
    const op = jest.fn().mockRejectedValue(new Error("permanent failure"));

    await expect(
      withRetry(op, {
        maxAttempts: 3,
        baseDelayMs: 0,
        maxDelayMs: 0,
        timeoutMs: 0,
      })
    ).rejects.toThrow("permanent failure");
    expect(op).toHaveBeenCalledTimes(3);
  });

  it("passes the attempt index to the operation factory", async () => {
    const attempts: number[] = [];
    const op = jest.fn().mockImplementation((attempt: number) => {
      attempts.push(attempt);
      return Promise.reject(new Error("fail"));
    });

    await expect(
      withRetry(op, {
        maxAttempts: 3,
        baseDelayMs: 0,
        maxDelayMs: 0,
        timeoutMs: 0,
      })
    ).rejects.toThrow();

    expect(attempts).toEqual([0, 1, 2]);
  });
});

describe("computeBackoffDelay", () => {
  it("returns a value between 0 and the capped exponential", () => {
    for (let attempt = 0; attempt < 5; attempt++) {
      const delay = computeBackoffDelay(attempt, 100, 5000);
      const maxExpected = Math.min(100 * Math.pow(2, attempt), 5000);
      expect(delay).toBeGreaterThanOrEqual(0);
      expect(delay).toBeLessThanOrEqual(maxExpected);
    }
  });

  it("respects the maxDelayMs cap", () => {
    const delay = computeBackoffDelay(100, 100, 1000);
    expect(delay).toBeLessThanOrEqual(1000);
  });
});
