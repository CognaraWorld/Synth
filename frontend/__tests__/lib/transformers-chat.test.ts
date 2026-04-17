import { describe, expect, it } from "vitest";
import {
  transformChatMessage,
  type BackendChatMessageResponse,
} from "@/lib/transformers/chat";

describe("transformChatMessage", () => {
  it("maps every backend field to the UI model", () => {
    const backend: BackendChatMessageResponse = {
      id: "msg-1",
      role: "assistant",
      content: "hello world",
      created_at: "2026-04-17T00:00:00Z",
      citations: [
        { type: "transcript", timestamp: "00:12", raw: "[T:00:12]" },
      ],
      tool_calls: [
        {
          tool_name: "web_search",
          input: { query: "hello" },
          output_summary: "one match",
        },
      ],
    };

    expect(transformChatMessage(backend)).toEqual({
      id: "msg-1",
      role: "assistant",
      content: "hello world",
      createdAt: "2026-04-17T00:00:00Z",
      citations: [{ type: "transcript", timestamp: "00:12", raw: "[T:00:12]" }],
      toolCalls: [
        {
          tool_name: "web_search",
          input: { query: "hello" },
          output_summary: "one match",
        },
      ],
    });
  });

  it("coerces the id to string even when the backend returns a number", () => {
    const backend = {
      id: 42 as unknown as string,
      role: "user" as const,
      content: "numeric id",
      created_at: "2026-04-17T00:00:00Z",
    };
    expect(transformChatMessage(backend).id).toBe("42");
  });

  it("defaults citations and toolCalls to null when absent", () => {
    const result = transformChatMessage({
      id: "m",
      role: "user",
      content: "x",
      created_at: "2026-04-17T00:00:00Z",
    });
    expect(result.citations).toBeNull();
    expect(result.toolCalls).toBeNull();
  });
});
