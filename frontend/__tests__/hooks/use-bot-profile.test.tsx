import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useBotProfile } from "@/hooks/use-bot-profile";
import type { BotProfileDTO } from "@/types";

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

function makeBotProfile(overrides: Partial<BotProfileDTO> = {}): BotProfileDTO {
  return {
    id: "bot-1",
    name: "Nova",
    persona: "Helpful assistant",
    voice: "FEMALE",
    responseMode: "WAKE_WORD_ONLY",
    createdAt: "2026-04-17T00:00:00.000Z",
    updatedAt: "2026-04-17T00:00:00.000Z",
    documents: [],
    ...overrides,
  };
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe("useBotProfile", () => {
  let fetchMock: FetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches /api/bot-profile on mount and exposes the result", async () => {
    const bot = makeBotProfile();
    fetchMock.mockResolvedValue(jsonResponse({ data: bot }));

    const { result } = renderHook(() => useBotProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(bot);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/api/bot-profile");
  });

  it("honors initialData and exposes it immediately", () => {
    const initialBot = makeBotProfile({ name: "Seeded Bot" });

    const { result } = renderHook(() => useBotProfile({ initialData: initialBot }), {
      wrapper: createWrapper(),
    });

    expect(result.current.data).toEqual(initialBot);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("updates the bot profile via PUT and writes the response into the cache", async () => {
    const initialBot = makeBotProfile();
    const updatedBot = makeBotProfile({ name: "Atlas", updatedAt: "2026-04-18T00:00:00.000Z" });

    fetchMock.mockImplementation((_input: string | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return Promise.resolve(jsonResponse({ data: updatedBot }));
      }
      return Promise.resolve(jsonResponse({ data: initialBot }));
    });

    const { result } = renderHook(() => useBotProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(initialBot);
    });

    await act(async () => {
      await result.current.updateBotProfile({ name: "Atlas" });
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(updatedBot);
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/bot-profile", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: "Atlas" }),
    });
  });

  it("surfaces fetch failures via error / isError", async () => {
    fetchMock.mockResolvedValue(errorJsonResponse(500, "backend down"));

    const { result } = renderHook(() => useBotProfile(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect((result.current.error as Error).message).toBe("Failed to load bot profile");
  });
});
