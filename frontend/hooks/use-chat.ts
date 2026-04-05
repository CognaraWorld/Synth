"use client";

import { useCallback, useEffect, useState } from "react";
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

  useEffect(() => {
    setMessages([]);
    setHistoryLoaded(false);
    setError(null);
  }, [meetingId]);

  // Load most recent messages (backend returns newest N in chronological order)
  useEffect(() => {
    if (!meetingId || historyLoaded) return;

    fetch(`/api/chat/${meetingId}?per_page=50`, { cache: "no-store" })
      .then((response) => response.json())
      .then((data: { data?: BackendChatHistoryResponse }) => {
        if (data.data?.messages) {
          setMessages(data.data.messages.map(transformChatMessage));
        }
        setHistoryLoaded(true);
      })
      .catch(() => setHistoryLoaded(true));
  }, [historyLoaded, meetingId]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;
      setError(null);

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
        const response = await fetch(`/api/chat/${meetingId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text }),
        });

        if (!response.ok) {
          const body = await response.json().catch(() => null) as { error?: string } | null;
          throw new Error(body?.error || "Chat request failed");
        }

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
        setMessages((current) => current.filter((message) => message.id !== tempId));
        setError(err instanceof Error ? err.message : "Failed to send message. Try again.");
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, meetingId]
  );

  return { messages, sendMessage, isLoading, error };
}
