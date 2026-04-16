/**
 * Tests for the SSE reader that powers streaming chat + insights.
 *
 * Pattern (follow this for other lib tests):
 *   1. Build a minimal ReadableStream that mimics the backend's SSE output.
 *   2. Wrap it in a Response so readSSE can treat it like a real fetch response.
 *   3. Drive the async generator, asserting the sequence of yielded events.
 *   4. Exercise abort + edge cases (no body, malformed JSON, multi-line chunks).
 */

import { describe, expect, it, vi } from "vitest";
import { readSSE } from "@/lib/sse-reader";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

function responseWithBody(body: ReadableStream<Uint8Array> | null): Response {
  // Response's second-arg constructor is picky about stream types in jsdom,
  // so we build it manually with the minimum shape readSSE touches.
  return {
    body,
  } as unknown as Response;
}

describe("readSSE", () => {
  it("yields each parsed SSE event in order", async () => {
    const stream = streamFromChunks([
      'data: {"type":"token","content":"hello"}\n\n',
      'data: {"type":"token","content":"world"}\n\n',
      'data: {"type":"done"}\n\n',
    ]);

    const events: unknown[] = [];
    for await (const evt of readSSE(responseWithBody(stream))) {
      events.push(evt);
    }

    expect(events).toEqual([
      { type: "token", content: "hello" },
      { type: "token", content: "world" },
      { type: "done" },
    ]);
  });

  it("handles events split across multiple chunks", async () => {
    // A real server may flush `data: {"type":"to` in one frame and `ken"}\n\n`
    // in another. The reader must buffer until it sees a newline.
    const stream = streamFromChunks([
      'data: {"type":"to',
      'ken","content":"split"}\n',
      "\n",
    ]);

    const events: unknown[] = [];
    for await (const evt of readSSE(responseWithBody(stream))) {
      events.push(evt);
    }

    expect(events).toEqual([{ type: "token", content: "split" }]);
  });

  it("skips malformed JSON without aborting the stream", async () => {
    const stream = streamFromChunks([
      "data: not-json\n\n",
      'data: {"type":"token","content":"survived"}\n\n',
    ]);

    const events: unknown[] = [];
    for await (const evt of readSSE(responseWithBody(stream))) {
      events.push(evt);
    }

    expect(events).toEqual([{ type: "token", content: "survived" }]);
  });

  it("ignores lines that do not start with `data: `", async () => {
    const stream = streamFromChunks([
      "event: ping\n",
      "retry: 1000\n",
      'data: {"type":"token","content":"only"}\n\n',
    ]);

    const events: unknown[] = [];
    for await (const evt of readSSE(responseWithBody(stream))) {
      events.push(evt);
    }

    expect(events).toEqual([{ type: "token", content: "only" }]);
  });

  it("returns immediately when response.body is null", async () => {
    const events: unknown[] = [];
    for await (const evt of readSSE(responseWithBody(null))) {
      events.push(evt);
    }
    expect(events).toEqual([]);
  });

  it("cancels the underlying reader when the abort signal fires", async () => {
    // Build a stream we can control frame-by-frame.
    let controllerRef!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controllerRef = controller;
      },
    });

    const encoder = new TextEncoder();
    const abortController = new AbortController();
    const reader = stream.getReader();
    // Spy on the real reader object we'll hand back to readSSE.
    const cancelSpy = vi.spyOn(reader, "cancel");

    const response = {
      body: {
        getReader: () => reader,
      },
    } as unknown as Response;

    const events: unknown[] = [];
    const consumer = (async () => {
      for await (const evt of readSSE(response, abortController.signal)) {
        events.push(evt);
      }
    })();

    // Emit one event so the reader is actively awaiting the next read.
    controllerRef.enqueue(encoder.encode('data: {"type":"first"}\n\n'));
    // Give the generator a microtask tick to process.
    await new Promise((r) => setTimeout(r, 0));

    // Now abort — readSSE should call reader.cancel() and the loop should exit.
    abortController.abort();
    await consumer;

    expect(cancelSpy).toHaveBeenCalled();
    expect(events).toEqual([{ type: "first" }]);
  });
});
