"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type BackendChatHistoryResponse,
  type BackendChatResponse,
  type ChatMessage,
  transformChatMessage,
} from "@/lib/transformers/chat";

export function useChat(meetingId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const meetingIdRef = useRef(meetingId);

  useEffect(() => {
    meetingIdRef.current = meetingId;
    setMessages([]);
    setHistoryLoaded(false);
    setError(null);
  }, [meetingId]);

  // Load most recent messages with AbortController for cleanup
  useEffect(() => {
    if (!meetingId || historyLoaded) return;

    const controller = new AbortController();

    fetch(`/api/chat/${meetingId}?per_page=50`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => response.json())
      .then((data: { data?: BackendChatHistoryResponse }) => {
        if (controller.signal.aborted) return;
        if (data.data?.messages) {
          setMessages(data.data.messages.map(transformChatMessage));
        }
        setHistoryLoaded(true);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setHistoryLoaded(true);
      });

    return () => controller.abort();
  }, [historyLoaded, meetingId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;
      setError(null);

      const currentMeetingId = meetingIdRef.current;
      const tempId = `temp_${Date.now()}`;
      const userMessage: ChatMessage = {
        id: tempId,
        role: "user",
        content: text,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, userMessage]);
      setIsLoading(true);

      try {
        const response = await fetch(`/api/chat/${currentMeetingId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        });

        if (!response.ok) {
          const body = (await response.json().catch(() => null)) as { error?: string } | null;
          throw new Error(body?.error || "Chat request failed");
        }

        // Guard against stale response if meetingId changed during the request
        if (meetingIdRef.current !== currentMeetingId) return;

        const data = (await response.json()) as { data: BackendChatResponse };
        setMessages((current) => {
          const withoutTemp = current.filter((message) => message.id !== tempId);
          return [
            ...withoutTemp,
            transformChatMessage(data.data.user_message),
            transformChatMessage(data.data.assistant_message),
          ];
        });
      } catch (err) {
        if (meetingIdRef.current !== currentMeetingId) return;
        setMessages((current) => current.filter((message) => message.id !== tempId));
        setError(err instanceof Error ? err.message : "Failed to send message. Try again.");
      } finally {
        if (meetingIdRef.current === currentMeetingId) {
          setIsLoading(false);
        }
      }
    },
    [isLoading]
  );

  return { messages, sendMessage, isLoading, error };
}
