import { NextResponse } from "next/server";
import { getBackendToken } from "@/lib/auth/session";

export async function GET() {
  const token = await getBackendToken();
  if (!token) {
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  return NextResponse.json({ token });
}
