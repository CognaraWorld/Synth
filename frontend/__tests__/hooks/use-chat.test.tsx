/**
 * Tests for useChat — the streaming chat hook.
 *
 * Pattern (follow this for every hook test):
 *   1. Render the hook with renderHook() from @testing-library/react.
 *   2. Mock global fetch for every network call; return shaped data
 *      or an SSE ReadableStream as appropriate.
 *   3. Drive the hook by calling exposed methods (sendMessage, stopStreaming, …).
 *   4. Use `waitFor` to assert state transitions — React state updates
 *      are async and won't be visible inside the same microtask.
 *   5. Clean up the fetch mock in afterEach so tests stay isolated.
 *
 * What this file covers:
 *   - history load on mount (success + failure path surfaces error state)
 *   - sendMessage streaming flow — token events accumulate, done swaps ids
 *   - explicit stopStreaming aborts the in-flight stream cleanly
 *   - meetingId change resets messages / error / streaming state
 *   - cross-meeting path uses the non-streaming endpoint
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChat } from "@/hooks/use-chat";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function errorJsonResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ error: detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(events: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of events) {
        controller.enqueue(encoder.encode(frame));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function emptyHistoryResponse(): Response {
  return jsonResponse({ data: { messages: [], meeting_id: "m1", total: 0 } });
}

const EMPTY_SUGGESTIONS = jsonResponse({ data: { suggestions: [] } });

describe("useChat", () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("loads chat history on mount and populates messages", async () => {
    fetchMock.mockImplementation((input: string | URL) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      if (url.includes("/api/chat/")) {
        return Promise.resolve(
          jsonResponse({
            data: {
              meeting_id: "m1",
              total: 2,
              messages: [
                { id: "u1", role: "user", content: "hi", created_at: "2026-04-17T00:00:00Z" },
                {
                  id: "a1",
                  role: "assistant",
                  content: "hello back",
                  created_at: "2026-04-17T00:00:01Z",
                },
              ],
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });

    const { result } = renderHook(() => useChat("m1"));

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(2);
    });
    expect(result.current.messages[0].content).toBe("hi");
    expect(result.current.messages[1].content).toBe("hello back");
    expect(result.current.error).toBeNull();
  });

  it("surfaces an error when history load fails", async () => {
    fetchMock.mockImplementation((input: string | URL) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      return Promise.resolve(errorJsonResponse(500, "backend down"));
    });

    const { result } = renderHook(() => useChat("m1"));

    await waitFor(() => {
      expect(result.current.error).toBe("backend down");
    });
  });

  it("streams an assistant response and finalises ids on done", async () => {
    fetchMock.mockImplementation((input: string | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      if (url.endsWith("/stream") && init?.method === "POST") {
        return Promise.resolve(
          sseResponse([
            'data: {"type":"token","content":"Hello"}\n\n',
            'data: {"type":"token","content":"there."}\n\n',
            'data: {"type":"done","user_message_id":"u-final","assistant_message_id":"a-final","follow_ups":["ok?"]}\n\n',
          ]),
        );
      }
      // First GET is the history load — return empty.
      return Promise.resolve(emptyHistoryResponse());
    });

    const { result } = renderHook(() => useChat("m1"));
    await waitFor(() => expect(result.current.messages).toEqual([]));

    await act(async () => {
      await result.current.sendMessage("ping");
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isStreaming).toBe(false);
    });

    const ids = result.current.messages.map((m) => m.id);
    expect(ids).toContain("u-final");
    expect(ids).toContain("a-final");
    const assistant = result.current.messages.find((m) => m.id === "a-final");
    expect(assistant?.content).toBe("Hello there.");
    expect(result.current.followUps).toEqual(["ok?"]);
  });

  it("stopStreaming aborts the in-flight stream and clears the placeholder", async () => {
    // This stream will never finish — sendMessage relies on abort to unwind.
    fetchMock.mockImplementation((input: string | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      if (url.endsWith("/stream") && init?.method === "POST") {
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            const encoder = new TextEncoder();
            controller.enqueue(encoder.encode('data: {"type":"token","content":"partial"}\n\n'));
            // Leave the stream open so the consumer blocks on read.
          },
        });
        return Promise.resolve(
          new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
        );
      }
      if (url.includes("/api/chat/")) {
        // Resync after abort — return empty history.
        return Promise.resolve(emptyHistoryResponse());
      }
      return Promise.resolve(jsonResponse({}));
    });

    const { result } = renderHook(() => useChat("m1"));
    await waitFor(() => expect(result.current.messages).toEqual([]));

    // Kick off the send without awaiting — it will never resolve on its own.
    let sendPromise!: Promise<void>;
    act(() => {
      sendPromise = result.current.sendMessage("never resolves");
    });

    // Let the first token arrive so isStreaming flips true.
    await waitFor(() => expect(result.current.isStreaming).toBe(true));

    // Abort the stream.
    act(() => {
      result.current.stopStreaming();
    });

    await act(async () => {
      await sendPromise;
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
      expect(result.current.isLoading).toBe(false);
    });
    await waitFor(() => {
      expect(result.current.messages.every((m) => !m.id.startsWith("temp_"))).toBe(true);
      expect(result.current.messages.every((m) => !m.id.startsWith("streaming_"))).toBe(true);
    });
  });

  it("resets messages and error state when meetingId changes", async () => {
    fetchMock.mockImplementation((input: string | URL) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      if (url.includes("/api/chat/m1")) {
        return Promise.resolve(
          jsonResponse({
            data: {
              meeting_id: "m1",
              total: 1,
              messages: [
                { id: "u1", role: "user", content: "in m1", created_at: "2026-04-17T00:00:00Z" },
              ],
            },
          }),
        );
      }
      if (url.includes("/api/chat/m2")) {
        return Promise.resolve(
          jsonResponse({
            data: { meeting_id: "m2", total: 0, messages: [] },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });

    const { result, rerender } = renderHook(
      ({ id }: { id: string }) => useChat(id),
      { initialProps: { id: "m1" } },
    );

    await waitFor(() => expect(result.current.messages).toHaveLength(1));

    rerender({ id: "m2" });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(0);
      expect(result.current.error).toBeNull();
    });
  });

  it("cross-meeting mode hits /api/chat/cross-meeting and bypasses streaming", async () => {
    fetchMock.mockImplementation((input: string | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/suggestions")) return Promise.resolve(EMPTY_SUGGESTIONS);
      if (url.endsWith("/api/chat/cross-meeting") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            data: {
              user_message: {
                id: "cu1",
                role: "user",
                content: "span meetings",
                created_at: "2026-04-17T00:00:00Z",
              },
              assistant_message: {
                id: "ca1",
                role: "assistant",
                content: "here is a cross summary",
                created_at: "2026-04-17T00:00:01Z",
              },
              follow_ups: ["another?"],
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });

    const { result } = renderHook(() =>
      useChat("cross", { crossMeeting: true }),
    );

    await act(async () => {
      await result.current.sendMessage("span meetings");
    });

    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[1].content).toBe("here is a cross summary");
    expect(result.current.followUps).toEqual(["another?"]);
    // Streaming endpoint must not have been called.
    const streamCalls = fetchMock.mock.calls.filter(([u]) =>
      String(u).endsWith("/stream"),
    );
    expect(streamCalls).toHaveLength(0);
  });
});
