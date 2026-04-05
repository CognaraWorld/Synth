import "server-only";

import { NextResponse } from "next/server";
import { errorResponse } from "@/lib/api-response";
import { BackendError } from "@/lib/backend-client";
import { getBackendToken } from "@/lib/auth/session";

export async function requireBackendToken() {
  return getBackendToken();
}

export function notAuthenticatedResponse() {
  return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
}

export function backendErrorResponse(error: unknown, fallback = "Request failed") {
  if (error instanceof BackendError) {
    return errorResponse(error.detail, error.status);
  }

  const message = error instanceof Error ? error.message : fallback;
  return errorResponse(message, 500);
}
