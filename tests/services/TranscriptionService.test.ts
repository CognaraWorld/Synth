import { TranscriptionService, StubTranscriptionProvider } from "../../src/services/TranscriptionService";

describe("TranscriptionService", () => {
  const provider = new StubTranscriptionProvider();
  const service = new TranscriptionService({ provider });

  it("returns a Transcript with the correct recordingId and ownerId", async () => {
    const transcript = await service.transcribe(
      "rec-1",
      "user-1",
      "https://example.com/audio.mp3"
    );

    expect(transcript.recordingId).toBe("rec-1");
    expect(transcript.ownerId).toBe("user-1");
  });

  it("returns a Transcript with a non-empty text", async () => {
    const transcript = await service.transcribe(
      "rec-1",
      "user-1",
      "https://example.com/audio.mp3"
    );
    expect(transcript.text.length).toBeGreaterThan(0);
  });

  it("assigns a unique id to each transcript", async () => {
    const t1 = await service.transcribe("rec-1", "user-1", "https://example.com/a.mp3");
    const t2 = await service.transcribe("rec-1", "user-1", "https://example.com/a.mp3");
    expect(t1.id).not.toBe(t2.id);
  });

  it("sanitizes provider output (removes null bytes)", async () => {
    const maliciousProvider = {
      transcribeAudio: jest
        .fn()
        .mockResolvedValue("Hello\0World"),
    };
    const s = new TranscriptionService({ provider: maliciousProvider });
    const transcript = await s.transcribe(
      "rec-2",
      "user-1",
      "https://example.com/audio.mp3"
    );
    expect(transcript.text).toBe("HelloWorld");
  });

  it("throws when the audio URL is not HTTPS", async () => {
    await expect(
      service.transcribe("rec-1", "user-1", "http://example.com/audio.mp3")
    ).rejects.toThrow(/must use HTTPS/);
  });

  it("sets the language field from the parameter (defaults to en-US)", async () => {
    const transcript = await service.transcribe(
      "rec-1",
      "user-1",
      "https://example.com/audio.mp3"
    );
    expect(transcript.language).toBe("en-US");

    const transcript2 = await service.transcribe(
      "rec-1",
      "user-1",
      "https://example.com/audio.mp3",
      "fr-FR"
    );
    expect(transcript2.language).toBe("fr-FR");
  });
});
