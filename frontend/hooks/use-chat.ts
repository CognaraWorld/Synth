"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { readSSE } from "@/lib/sse-reader";
import {
  type BackendChatResponse,
  type BackendChatHistoryResponse,
  type CitationReference,
  type ChatMessage,
  type ToolCallInfo,
  transformChatMessage,
} from "@/lib/transformers/chat";

type StreamEvent =
  | { type: "token"; content: string }
  | {
      type: "done";
      user_message_id: string;
      assistant_message_id: string;
      follow_ups?: string[];
      citations?: CitationReference[] | null;
      tool_calls?: ToolCallInfo[] | null;
    }
  | { type: "error"; content: string };

function appendStreamContent(current: string, next: string) {
  if (!current) return next;
  // Backend yields stripped sentences — add space between them to preserve readability
  return current + " " + next;
}

async function readErrorMessage(response: Response) {
  const body = (await response.json().catch(() => null)) as { error?: string } | null;
  return body?.error || "Chat request failed";
}

export function useChat(meetingId: string, options?: { crossMeeting?: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [followUps, setFollowUps] = useState<string[]>([]);
  const meetingIdRef = useRef(meetingId);
  const streamAbortRef = useRef<AbortController | null>(null);
  const resyncAbortRef = useRef<AbortController | null>(null);
  const isLoadingRef = useRef(false);
  const isStreamingRef = useRef(false);
  const crossMeeting = options?.crossMeeting ?? false;

  const loadHistory = useCallback(async (targetMeetingId: string, signal?: AbortSignal) => {
    const response = await fetch(`/api/chat/${targetMeetingId}?per_page=50`, {
      cache: "no-store",
      signal,
    });

    if (!response.ok) {
      throw new Error(await readErrorMessage(response));
    }

    const data = (await response.json()) as { data?: BackendChatHistoryResponse };
    return data.data?.messages?.map(transformChatMessage) ?? [];
  }, []);

  useEffect(() => {
    meetingIdRef.current = meetingId;
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;
    resyncAbortRef.current?.abort();
    resyncAbortRef.current = null;
    isLoadingRef.current = false;
    isStreamingRef.current = false;
    setMessages([]);
    setHistoryLoaded(crossMeeting);
    setError(null);
    setIsLoading(false);
    setIsStreaming(false);
    setSuggestions([]);
    setFollowUps([]);
  }, [crossMeeting, meetingId]);

  useEffect(() => {
    if (!meetingId || historyLoaded || crossMeeting) return;

    const controller = new AbortController();

    loadHistory(meetingId, controller.signal)
      .then((history) => {
        if (controller.signal.aborted || meetingIdRef.current !== meetingId) return;
        setMessages(history);
        setHistoryLoaded(true);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (meetingIdRef.current !== meetingId) return;
        setHistoryLoaded(true);
      });

    return () => controller.abort();
  }, [crossMeeting, historyLoaded, loadHistory, meetingId]);

  useEffect(() => {
    if (!meetingId || crossMeeting) return;

    const controller = new AbortController();

    fetch(`/api/chat/${meetingId}/suggestions`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((response) => response.json())
      .then((data: { data?: { suggestions?: string[] } }) => {
        if (!controller.signal.aborted && data.data?.suggestions) {
          setSuggestions(data.data.suggestions);
        }
      })
      .catch(() => {});

    return () => controller.abort();
  }, [crossMeeting, meetingId]);

  const stopStreaming = useCallback(() => {
    streamAbortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoadingRef.current || isStreamingRef.current) return;

      resyncAbortRef.current?.abort();
      resyncAbortRef.current = null;
      setError(null);
      setFollowUps([]);
      const currentMeetingId = meetingIdRef.current;
      const tempUserId = `temp_user_${Date.now()}`;
      const streamingId = `streaming_${Date.now()}`;
      const userCreatedAt = new Date().toISOString();
      const assistantCreatedAt = new Date().toISOString();
      let assistantContent = "";
      let completed = false;

      setMessages((current) => [
        ...current,
        {
          id: tempUserId,
          role: "user",
          content: text,
          createdAt: userCreatedAt,
        },
      ]);
      setSuggestions([]);
      isLoadingRef.current = true;
      setIsLoading(true);

      const controller = new AbortController();
      streamAbortRef.current = controller;

      try {
        if (crossMeeting) {
          const response = await fetch("/api/chat/cross-meeting", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
            signal: controller.signal,
          });
          if (!response.ok) {
            throw new Error(await readErrorMessage(response));
          }

          const data = (await response.json()) as { data: BackendChatResponse };
          if (meetingIdRef.current !== currentMeetingId) return;

          setMessages((current) => {
            const withoutTemp = current.filter((message) => message.id !== tempUserId);
            return [
              ...withoutTemp,
              transformChatMessage(data.data.user_message),
              transformChatMessage(data.data.assistant_message),
            ];
          });
          if (data.data.follow_ups) {
            setFollowUps(data.data.follow_ups);
          }
        } else {
          const response = await fetch(`/api/chat/${currentMeetingId}/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
            signal: controller.signal,
          });

          if (!response.ok) {
            throw new Error(await readErrorMessage(response));
          }

          for await (const event of readSSE<StreamEvent>(response, controller.signal)) {
            if (meetingIdRef.current !== currentMeetingId) {
              return;
            }

            if (event.type === "token") {
              assistantContent = appendStreamContent(assistantContent, event.content);
              isLoadingRef.current = false;
              setIsLoading(false);
              isStreamingRef.current = true;
              setIsStreaming(true);
              setMessages((current) => {
                const withoutStreaming = current.filter((message) => message.id !== streamingId);
                return [
                  ...withoutStreaming,
                  {
                    id: streamingId,
                    role: "assistant",
                    content: assistantContent,
                    createdAt: assistantCreatedAt,
                  },
                ];
              });
              continue;
            }

            if (event.type === "error") {
              throw new Error(event.content || "AI service temporarily unavailable.");
            }

            if (event.type === "done") {
              completed = true;
              setMessages((current) => {
                const hasStreamingMessage = current.some((message) => message.id === streamingId);
                const nextMessages = current.map((message) => {
                  if (message.id === tempUserId) {
                    return { ...message, id: event.user_message_id };
                  }
                  if (message.id === streamingId) {
                    return {
                      ...message,
                      id: event.assistant_message_id,
                      citations: event.citations ?? null,
                      toolCalls: event.tool_calls ?? null,
                    };
                  }
                  return message;
                });

                if (hasStreamingMessage) {
                  return nextMessages;
                }

                return [
                  ...nextMessages,
                  {
                    id: event.assistant_message_id,
                    role: "assistant",
                    content: assistantContent,
                    createdAt: assistantCreatedAt,
                    citations: event.citations ?? null,
                    toolCalls: event.tool_calls ?? null,
                  },
                ];
              });
              if (event.follow_ups) {
                setFollowUps(event.follow_ups);
              }
              break;
            }
          }

          if (!completed && !controller.signal.aborted) {
            throw new Error("Stream ended unexpectedly.");
          }
        }
      } catch (err) {
        if (meetingIdRef.current !== currentMeetingId) return;

        if (err instanceof DOMException && err.name === "AbortError") {
          setMessages((current) =>
            current.filter((message) => message.id !== tempUserId && message.id !== streamingId)
          );

          if (!crossMeeting) {
            try {
              const resyncController = new AbortController();
              resyncAbortRef.current = resyncController;
              const history = await loadHistory(currentMeetingId, resyncController.signal);
              if (meetingIdRef.current === currentMeetingId && !resyncController.signal.aborted) {
                setMessages(history);
              }
            } catch {
              // Ignore sync failure after an abort.
            }
          }
          return;
        }

        setMessages((current) =>
          current.filter((message) => message.id !== tempUserId && message.id !== streamingId)
        );
        setError(err instanceof Error ? err.message : "Failed to send message. Try again.");
      } finally {
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null;
        }
        if (meetingIdRef.current === currentMeetingId) {
          isLoadingRef.current = false;
          isStreamingRef.current = false;
          setIsLoading(false);
          setIsStreaming(false);
        }
      }
    },
    [crossMeeting, loadHistory]
  );

  return { messages, sendMessage, isLoading, isStreaming, error, stopStreaming, suggestions, followUps };
}
