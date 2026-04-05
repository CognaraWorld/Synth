"use client";

import { useQuery } from "@tanstack/react-query";

export interface LiveSessionResponse {
  meeting_id: string;
  meeting_status: string;
  platform: string;
  meeting_link: string;
  engine_session_id?: string | null;
  provider_bot_id?: string | null;
  session_status: string;
  is_active: boolean;
  is_muted: boolean;
  stop_requested: boolean;
  websocket_path?: string | null;
  transcript_length: number;
  last_instruction_at?: string | null;
  last_transcript_at?: string | null;
  provider_last_error?: string | null;
  created_at: string;
  updated_at: string;
  ended_at?: string | null;
}

export function useLiveSession(meetingId: string | undefined) {
  return useQuery({
    queryKey: ["live-session", meetingId],
    queryFn: async () => {
      const response = await fetch(`/api/live-sessions/${meetingId}`, {
        cache: "no-store"
      });

      if (!response.ok) {
        throw new Error("Failed to load live session");
      }

      const result = (await response.json()) as { data: LiveSessionResponse };
      return result.data;
    },
    enabled: !!meetingId,
    refetchInterval: 5000
  });
}
