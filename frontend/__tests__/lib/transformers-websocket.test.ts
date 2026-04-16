/**
 * Tests for transformWsMessage — the WebSocket ingress type narrower.
 *
 * Pattern (follow this for other transformer tests):
 *   1. Feed both well-formed payloads and deliberately hostile ones.
 *   2. Assert the shape of the narrowed DashboardWsMessage result.
 *   3. Cover null/undefined/primitive inputs so unknown-typed inputs
 *      cannot sneak past the guard.
 */

import { describe, expect, it } from "vitest";
import { transformWsMessage } from "@/lib/transformers/websocket";

describe("transformWsMessage", () => {
  describe("transcript messages", () => {
    it("maps a well-formed transcript payload to a chunk", () => {
      const result = transformWsMessage({
        type: "transcript",
        text: "hello world",
        speaker: "Alice",
        timestamp: "2026-04-17T00:00:00.000Z",
      });

      expect(result?.type).toBe("chunk");
      if (result?.type !== "chunk") return;
      expect(result.payload.text).toBe("hello world");
      expect(result.payload.speaker).toBe("Alice");
      expect(result.payload.timestamp).toBe("2026-04-17T00:00:00.000Z");
      expect(result.payload.isBot).toBe(false);
      // id should be a generated chunk_* string.
      expect(result.payload.id).toMatch(/^chunk_/);
    });

    it("flags the bot's own output via speaker name", () => {
      const resultSynth = transformWsMessage({
        type: "transcript",
        text: "I am the bot",
        speaker: "Synth",
      });
      const resultCognara = transformWsMessage({
        type: "transcript",
        text: "I am also the bot",
        speaker: "Cognara Assistant",
      });

      expect(resultSynth?.type === "chunk" && resultSynth.payload.isBot).toBe(true);
      expect(resultCognara?.type === "chunk" && resultCognara.payload.isBot).toBe(true);
    });

    it("returns null when the transcript text is missing or not a string", () => {
      expect(transformWsMessage({ type: "transcript", text: "" })).toBeNull();
      expect(transformWsMessage({ type: "transcript", text: null })).toBeNull();
      expect(transformWsMessage({ type: "transcript", text: { nope: 1 } })).toBeNull();
      expect(transformWsMessage({ type: "transcript" })).toBeNull();
    });

    it("falls back to defaults for optional fields", () => {
      const result = transformWsMessage({ type: "transcript", text: "just text" });
      expect(result?.type).toBe("chunk");
      if (result?.type !== "chunk") return;
      expect(result.payload.speaker).toBe("Participant");
      // timestamp should still be a valid ISO string.
      expect(() => new Date(result.payload.timestamp).toISOString()).not.toThrow();
    });
  });

  describe("status messages", () => {
    it.each([
      ["listening", "LISTENING"],
      ["speaking", "SPEAKING"],
      ["joining", "THINKING"],
      ["responding", "SPEAKING"],
    ] as const)("maps backend state %s → UI status %s", (state, expected) => {
      const result = transformWsMessage({ type: "status", state });
      expect(result?.type).toBe("status");
      if (result?.type !== "status") return;
      expect(result.payload.status).toBe(expected);
    });

    it("defaults unknown states to LISTENING", () => {
      const result = transformWsMessage({ type: "status", state: "totally-made-up" });
      expect(result?.type).toBe("status");
      if (result?.type !== "status") return;
      expect(result.payload.status).toBe("LISTENING");
    });
  });

  describe("reset messages", () => {
    it("treats 'ended' and 'error' as reset triggers", () => {
      expect(transformWsMessage({ type: "ended" })).toEqual({ type: "reset", payload: null });
      expect(transformWsMessage({ type: "error" })).toEqual({ type: "reset", payload: null });
    });
  });

  describe("hostile / malformed inputs", () => {
    it.each([null, undefined, 0, "string", [1, 2, 3], true])(
      "returns null for non-object input (%j)",
      (input) => {
        expect(transformWsMessage(input)).toBeNull();
      },
    );

    it("returns null for objects without a recognised type", () => {
      expect(transformWsMessage({ type: "unknown-type" })).toBeNull();
      expect(transformWsMessage({})).toBeNull();
    });
  });
});
