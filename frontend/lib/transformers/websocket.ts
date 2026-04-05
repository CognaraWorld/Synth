import type { TranscriptChunkDTO } from "@/types";

export type DashboardWsMessage =
  | { type: "chunk"; payload: TranscriptChunkDTO }
  | { type: "status"; payload: { status: "LISTENING" | "THINKING" | "SPEAKING" | "MUTED" } }
  | { type: "reset"; payload: null };

export function transformWsMessage(message: any): DashboardWsMessage | null {
  if (message?.type === "transcript") {
    return {
      type: "chunk",
      payload: {
        id: `chunk_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
        speaker: message.speaker || "Participant",
        text: message.text,
        timestamp: message.timestamp || new Date().toISOString(),
        isBot:
          (message.speaker || "").toLowerCase().includes("synth") ||
          (message.speaker || "").toLowerCase().includes("cognara")
      }
    };
  }

  if (message?.type === "status") {
    const statusMap: Record<string, "LISTENING" | "THINKING" | "SPEAKING" | "MUTED"> = {
      listening: "LISTENING",
      speaking: "SPEAKING",
      joining: "THINKING",
      responding: "SPEAKING"
    };

    return {
      type: "status",
      payload: {
        status: statusMap[message.state] || "LISTENING"
      }
    };
  }

  if (message?.type === "ended" || message?.type === "error") {
    return {
      type: "reset",
      payload: null
    };
  }

  return null;
}
