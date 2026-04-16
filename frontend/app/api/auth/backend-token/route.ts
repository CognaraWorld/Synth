import { NextResponse } from "next/server";

/**
 * Removed. This endpoint previously returned the raw backend JWT to the
 * browser so client code could authenticate the WebSocket connection.
 * That leaked a 24-hour session token into browser memory, DevTools,
 * and proxy access logs — a P0 finding in the 2026-04-16 audit.
 *
 * Use POST /api/auth/ws-ticket instead: it returns a 60-second
 * single-use ticket that can only be spent on the WebSocket upgrade.
 */
export async function GET() {
  return NextResponse.json(
    {
      error:
        "This endpoint has been removed. Use POST /api/auth/ws-ticket " +
        "to obtain a short-lived WebSocket credential instead.",
    },
    { status: 410 },
  );
}
