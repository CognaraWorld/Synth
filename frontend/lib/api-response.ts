import { NextResponse } from "next/server";

export function successResponse<T>(data: T, init?: ResponseInit) {
  return NextResponse.json({ data }, init);
}

export function errorResponse(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}
