import {
  sanitizeTranscriptText,
  sanitizeShortString,
  validateHttpsUrl,
  MAX_TRANSCRIPT_LENGTH,
  MAX_TITLE_LENGTH,
} from "../../src/utils/sanitize";

describe("sanitizeTranscriptText", () => {
  it("returns clean text unchanged", () => {
    const text = "Alice: Let's schedule a follow-up.\nBob: Agreed.";
    expect(sanitizeTranscriptText(text)).toBe(text);
  });

  it("removes null bytes", () => {
    expect(sanitizeTranscriptText("hello\0world")).toBe("helloworld");
  });

  it("normalizes Windows CRLF line endings to LF", () => {
    expect(sanitizeTranscriptText("line1\r\nline2")).toBe("line1\nline2");
  });

  it("normalizes bare CR line endings to LF", () => {
    expect(sanitizeTranscriptText("line1\rline2")).toBe("line1\nline2");
  });

  it("throws when the transcript exceeds the maximum length", () => {
    const oversized = "a".repeat(MAX_TRANSCRIPT_LENGTH + 1);
    expect(() => sanitizeTranscriptText(oversized)).toThrow(
      /exceeds the maximum allowed length/
    );
  });

  it("accepts a transcript exactly at the maximum length", () => {
    const atLimit = "a".repeat(MAX_TRANSCRIPT_LENGTH);
    expect(() => sanitizeTranscriptText(atLimit)).not.toThrow();
  });

  it("throws when the input is not a string", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(() => sanitizeTranscriptText(42 as any)).toThrow(
      /must be a string/
    );
  });
});

describe("sanitizeShortString", () => {
  it("trims surrounding whitespace", () => {
    expect(sanitizeShortString("  hello  ")).toBe("hello");
  });

  it("removes null bytes", () => {
    expect(sanitizeShortString("abc\0def")).toBe("abcdef");
  });

  it("throws when the string exceeds the maximum length", () => {
    const oversized = "a".repeat(MAX_TITLE_LENGTH + 1);
    expect(() => sanitizeShortString(oversized)).toThrow(
      /exceeds the maximum allowed length/
    );
  });
});

describe("validateHttpsUrl", () => {
  it("accepts a valid HTTPS URL", () => {
    expect(() =>
      validateHttpsUrl("https://example.com/audio.mp3")
    ).not.toThrow();
  });

  it("throws for an HTTP URL", () => {
    expect(() =>
      validateHttpsUrl("http://example.com/audio.mp3")
    ).toThrow(/must use HTTPS/);
  });

  it("throws for an invalid URL string", () => {
    expect(() => validateHttpsUrl("not-a-url")).toThrow(/Invalid URL/);
  });

  it("throws for an ftp URL", () => {
    expect(() => validateHttpsUrl("ftp://files.example.com/audio.mp3")).toThrow(
      /must use HTTPS/
    );
  });
});
