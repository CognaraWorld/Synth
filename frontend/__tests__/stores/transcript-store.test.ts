import { beforeEach, describe, expect, it } from "vitest";
import { useTranscriptStore } from "@/stores/transcript-store";
import type { TranscriptChunkDTO } from "@/types";

function makeChunk(id: string): TranscriptChunkDTO {
  return {
    id,
    speaker: "Participant",
    text: `chunk ${id}`,
    timestamp: "2026-04-17T00:00:00.000Z",
  };
}

describe("useTranscriptStore", () => {
  beforeEach(() => {
    useTranscriptStore.getState().reset();
  });

  it("addChunk appends to chunks", () => {
    useTranscriptStore.getState().addChunk(makeChunk("chunk-1"));

    expect(useTranscriptStore.getState().chunks).toEqual([makeChunk("chunk-1")]);
  });

  it("drops the oldest chunk when the store reaches 500 items", () => {
    for (let index = 0; index < 500; index += 1) {
      useTranscriptStore.getState().addChunk(makeChunk(`chunk-${index}`));
    }

    useTranscriptStore.getState().addChunk(makeChunk("chunk-500"));

    const { chunks } = useTranscriptStore.getState();
    expect(chunks).toHaveLength(500);
    expect(chunks[0]?.id).toBe("chunk-1");
    expect(chunks[chunks.length - 1]?.id).toBe("chunk-500");
  });

  it("setStatus, setHighlightChunkId, and reset update state as expected", () => {
    useTranscriptStore.getState().setStatus("SPEAKING");
    useTranscriptStore.getState().setHighlightChunkId("chunk-42");
    useTranscriptStore.getState().addChunk(makeChunk("chunk-42"));

    expect(useTranscriptStore.getState().status).toBe("SPEAKING");
    expect(useTranscriptStore.getState().highlightChunkId).toBe("chunk-42");
    expect(useTranscriptStore.getState().chunks).toHaveLength(1);

    useTranscriptStore.getState().reset();

    expect(useTranscriptStore.getState()).toMatchObject({
      chunks: [],
      status: "LISTENING",
      highlightChunkId: null,
    });
  });
});
