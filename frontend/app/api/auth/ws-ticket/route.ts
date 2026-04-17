import { NextResponse } from "next/server";
import { backendPostEmpty } from "@/lib/backend-client";
import {
  backendErrorResponse,
  notAuthenticatedResponse,
  requireBackendToken,
} from "@/lib/backend-proxy";

/**
 * Exchange the user's server-side backend JWT for a short-lived
 * WebSocket ticket. The ticket expires in 60 seconds, can only be
 * consumed once, and is the only credential the browser should ever
 * see — the underlying JWT never leaves the server.
 */
export async function POST() {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const ticket = await backendPostEmpty<{ ticket: string; expires_in: number }>(
      "/api/auth/ws-ticket",
      token,
    );
    return NextResponse.json(ticket, {
      // Tickets are single-use — don't let anything cache them.
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return backendErrorResponse(error, "Failed to issue websocket ticket");
  }
}
