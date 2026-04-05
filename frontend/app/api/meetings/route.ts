import { NextRequest } from "next/server";
import { getMeetings, createMeeting } from "@/lib/data/meetings";
import { successResponse, errorResponse } from "@/lib/api-response";

export async function GET() {
  const meetings = await getMeetings();
  return successResponse(meetings);
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const meeting = await createMeeting(body);
    return successResponse(meeting, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return errorResponse(message);
  }
}
