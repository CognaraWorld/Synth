import type { TranscriptChunkDTO } from "@/types";

export type DashboardWsMessage =
  | { type: "chunk"; payload: TranscriptChunkDTO }
  | { type: "status"; payload: { status: "LISTENING" | "THINKING" | "SPEAKING" | "MUTED" } }
  | { type: "reset"; payload: null };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function transformWsMessage(message: unknown): DashboardWsMessage | null {
  if (!isRecord(message)) return null;

  if (message.type === "transcript") {
    const text = asString(message.text);
    if (!text) return null;
    const speaker = asString(message.speaker, "Participant");
    const timestamp = asString(message.timestamp, new Date().toISOString());
    const speakerLower = speaker.toLowerCase();
    return {
      type: "chunk",
      payload: {
        id: `chunk_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        speaker,
        text,
        timestamp,
        isBot: speakerLower.includes("synth") || speakerLower.includes("cognara")
      }
    };
  }

  if (message.type === "status") {
    const statusMap: Record<string, "LISTENING" | "THINKING" | "SPEAKING" | "MUTED"> = {
      listening: "LISTENING",
      speaking: "SPEAKING",
      joining: "THINKING",
      responding: "SPEAKING"
    };
    const state = asString(message.state);

    return {
      type: "status",
      payload: {
        status: statusMap[state] || "LISTENING"
      }
    };
  }

  if (message.type === "ended" || message.type === "error") {
    return {
      type: "reset",
      payload: null
    };
  }

  return null;
}
