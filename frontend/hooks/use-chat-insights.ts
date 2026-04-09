"use client";

import { useEffect, useRef, useState } from "react";
import { readSSE } from "@/lib/sse-reader";

export interface ChatInsight {
  type: "insight";
  speaker: string;
  claim: string;
  correction: string;
}

const MAX_INSIGHTS = 100;
const MAX_RETRIES = 5;

export function useChatInsights(meetingId: string | undefined, enabled: boolean) {
  const [insights, setInsights] = useState<ChatInsight[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setInsights([]);
    setUnreadCount(0);

    if (!meetingId || !enabled) {
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;

    async function connect(retryCount = 0) {
      try {
        const response = await fetch(`/api/chat/${meetingId}/insights`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          if (!controller.signal.aborted && retryCount < MAX_RETRIES) {
            setTimeout(() => connect(retryCount + 1), Math.min(1000 * 2 ** retryCount, 30000));
          }
          return;
        }

        for await (const event of readSSE<ChatInsight>(response, controller.signal)) {
          if (event.type === "insight") {
            setInsights((current) => {
              const next = [...current, event];
              return next.length > MAX_INSIGHTS ? next.slice(-MAX_INSIGHTS) : next;
            });
            setUnreadCount((current) => current + 1);
          }
        }

        // Stream ended normally — reconnect after a short delay
        if (!controller.signal.aborted) {
          setTimeout(() => connect(0), 2000);
        }
      } catch {
        if (!controller.signal.aborted && retryCount < MAX_RETRIES) {
          setTimeout(() => connect(retryCount + 1), Math.min(1000 * 2 ** retryCount, 30000));
        }
      }
    }

    void connect();
    return () => controller.abort();
  }, [enabled, meetingId]);

  function clearUnread() {
    setUnreadCount(0);
  }

  return { insights, unreadCount, clearUnread };
}
