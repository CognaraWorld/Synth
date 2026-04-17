import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useChatInsights } from "@/hooks/use-chat-insights";

type FetchMock = ReturnType<typeof vi.fn>;

function errorJsonResponse(status: number, detail: string): Response {
  return new Response(JSON.stringify({ error: detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(events: string[], options?: { keepOpen?: boolean }): Response {
  const encoder = new TextEncoder();
  const keepOpen = options?.keepOpen ?? false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of events) {
        controller.enqueue(encoder.encode(frame));
      }
      if (!keepOpen) {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("useChatInsights", () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("appends insight events and increments unread count", async () => {
    fetchMock.mockResolvedValue(
      sseResponse(
        ['data: {"type":"insight","speaker":"Alice","claim":"Revenue grew 30%","correction":"It grew 20%."}\n\n'],
        { keepOpen: true },
      ),
    );

    const { result, unmount } = renderHook(() => useChatInsights("meeting-1", true));

    await waitFor(() => {
      expect(result.current.insights).toHaveLength(1);
    });
    expect(result.current.insights[0]).toEqual({
      type: "insight",
      speaker: "Alice",
      claim: "Revenue grew 30%",
      correction: "It grew 20%.",
    });
    expect(result.current.unreadCount).toBe(1);

    unmount();
  });

  it("does not reconnect when the endpoint returns 400", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock.mockResolvedValue(errorJsonResponse(400, "meeting not live"));

    const { unmount } = renderHook(() => useChatInsights("meeting-1", true));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    await vi.advanceTimersByTimeAsync(60_000);

    expect(fetchMock).toHaveBeenCalledTimes(1);

    unmount();
  });

  it("reconnects after 500 responses up to MAX_RETRIES", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchMock.mockResolvedValue(errorJsonResponse(500, "backend down"));

    const { unmount } = renderHook(() => useChatInsights("meeting-1", true));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    await vi.advanceTimersByTimeAsync(1_000 + 2_000 + 4_000 + 8_000 + 16_000 + 100);

    expect(fetchMock).toHaveBeenCalledTimes(6);

    await vi.advanceTimersByTimeAsync(60_000);

    expect(fetchMock).toHaveBeenCalledTimes(6);

    unmount();
  });

  it("clearUnread resets unreadCount to zero", async () => {
    fetchMock.mockResolvedValue(
      sseResponse(
        ['data: {"type":"insight","speaker":"Bob","claim":"We launch Friday","correction":"Launch is next Tuesday."}\n\n'],
        { keepOpen: true },
      ),
    );

    const { result, unmount } = renderHook(() => useChatInsights("meeting-1", true));

    await waitFor(() => {
      expect(result.current.unreadCount).toBe(1);
    });

    act(() => {
      result.current.clearUnread();
    });

    expect(result.current.unreadCount).toBe(0);

    unmount();
  });

  it("aborts cleanly when enabled flips to false", async () => {
    let signalRef: AbortSignal | undefined;
    fetchMock.mockImplementation((_input: string | URL, init?: RequestInit) => {
      signalRef = init?.signal as AbortSignal | undefined;
      return Promise.resolve(sseResponse([], { keepOpen: true }));
    });

    const { rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useChatInsights("meeting-1", enabled),
      { initialProps: { enabled: true } },
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    expect(signalRef?.aborted).toBe(false);

    rerender({ enabled: false });

    await waitFor(() => {
      expect(signalRef?.aborted).toBe(true);
    });
  });
});
