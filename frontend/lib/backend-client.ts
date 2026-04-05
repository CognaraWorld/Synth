import "server-only";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export class BackendError extends Error {
  constructor(
    public status: number,
    public detail: string
  ) {
    super(`Backend ${status}: ${detail}`);
  }
}

async function readJson(response: Response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

/**
 * Low-level fetch wrapper. Callers pass fully-built headers —
 * this function does NOT add auth or content-type headers itself.
 */
export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await readJson(response.clone());
    const detail =
      typeof body === "object" && body && "detail" in body && typeof body.detail === "string"
        ? body.detail
        : response.statusText;
    throw new BackendError(response.status, detail);
  }

  return response;
}

async function jsonRequest<T>(
  path: string,
  token: string,
  init?: RequestInit & { skipContentType?: boolean }
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (!init?.skipContentType && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await backendFetch(path, { ...init, headers });
  const body = await readJson(response);
  return (body ?? undefined) as T;
}

export function backendGet<T>(path: string, token: string): Promise<T> {
  return jsonRequest<T>(path, token);
}

export function backendPost<T>(path: string, body: unknown, token: string): Promise<T> {
  return jsonRequest<T>(path, token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function backendPostEmpty<T>(path: string, token: string): Promise<T> {
  return jsonRequest<T>(path, token, { method: "POST" });
}

export function backendPostForm<T>(path: string, body: FormData, token: string): Promise<T> {
  // FormData sets its own Content-Type with boundary — do not override.
  return jsonRequest<T>(path, token, {
    method: "POST",
    body,
    skipContentType: true,
  });
}

export function backendPut<T>(path: string, body: unknown, token: string): Promise<T> {
  return jsonRequest<T>(path, token, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function backendDelete<T>(path: string, token: string): Promise<T> {
  return jsonRequest<T>(path, token, { method: "DELETE" });
}
