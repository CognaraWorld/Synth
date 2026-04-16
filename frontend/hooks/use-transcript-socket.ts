"use client";

import { useEffect, useRef } from "react";
import { useLiveSession } from "@/hooks/use-live-session";
import { transformWsMessage } from "@/lib/transformers/websocket";
import { useTranscriptStore } from "@/stores/transcript-store";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

export function useTranscriptSocket(meetingId: string) {
  const { data: liveSession } = useLiveSession(meetingId || undefined);
  const addChunk = useTranscriptStore((state) => state.addChunk);
  const setStatus = useTranscriptStore((state) => state.setStatus);
  const reset = useTranscriptStore((state) => state.reset);
  const retriesRef = useRef(0);

  useEffect(() => {
    reset();
  }, [meetingId, reset]);

  useEffect(() => {
    const sessionId = liveSession?.engine_session_id;
    if (!meetingId || !sessionId) return;

    let socket: WebSocket | null = null;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    async function connect() {
      if (cancelled) return;

      try {
        // Trade the server-side JWT for a 60-second single-use ticket.
        // The raw JWT never reaches the browser, so a leaked URL/log
        // line can only be replayed for a minute and only once.
        const ticketResponse = await fetch("/api/auth/ws-ticket", {
          method: "POST",
          cache: "no-store",
        });
        if (!ticketResponse.ok || cancelled) return;

        const ticketData = (await ticketResponse.json()) as { ticket?: string };
        if (!ticketData.ticket || cancelled) return;

        const endpoint = `${process.env.NEXT_PUBLIC_BACKEND_WS_URL ?? "ws://localhost:8000"}/api/ws/${sessionId}?ticket=${encodeURIComponent(ticketData.ticket)}`;
        socket = new WebSocket(endpoint);

        socket.onopen = () => {
          retriesRef.current = 0;
        };

        socket.onmessage = (event) => {
          try {
            const parsed = JSON.parse(event.data) as unknown;
            const message = transformWsMessage(parsed);

            if (!message) return;
            if (message.type === "chunk" && message.payload) {
              addChunk(message.payload);
            }
            if (message.type === "status" && message.payload) {
              setStatus(message.payload.status);
            }
            if (message.type === "reset") {
              reset();
            }
          } catch {
            // Ignore malformed websocket payloads.
          }
        };

        socket.onclose = (event) => {
          if (cancelled) return;
          // 1000 = normal closure, 1001 = going away — don't reconnect
          if (event.code === 1000 || event.code === 1001) return;

          scheduleReconnect();
        };

        socket.onerror = () => {
          // onclose fires after onerror — reconnect handled there.
          socket?.close();
        };
      } catch {
        if (!cancelled) {
          scheduleReconnect();
        }
      }
    }

    function scheduleReconnect() {
      if (cancelled) return;
      const delay = Math.min(
        RECONNECT_BASE_MS * Math.pow(2, retriesRef.current),
        RECONNECT_MAX_MS
      );
      retriesRef.current += 1;
      reconnectTimer = setTimeout(() => void connect(), delay);
    }

    void connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [addChunk, liveSession?.engine_session_id, meetingId, reset, setStatus]);
}
