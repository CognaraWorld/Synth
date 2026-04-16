/**
 * Parse a ReadableStream of SSE events.
 * Yields parsed JSON objects from `data: {...}` lines.
 */
export async function* readSSE<T = unknown>(
  response: Response,
  signal?: AbortSignal
): AsyncGenerator<T> {
  const reader = response.body?.getReader();
  if (!reader) return;

  // Wire up abort signal to cancel the reader so reader.read() rejects
  // immediately instead of blocking until the server sends data.
  const onAbort = () => reader.cancel();
  signal?.addEventListener("abort", onAbort);

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data: ")) {
          try {
            yield JSON.parse(trimmed.slice(6)) as T;
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  } finally {
    signal?.removeEventListener("abort", onAbort);
    reader.releaseLock();
  }
}
