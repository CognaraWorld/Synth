import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma";
import { getCurrentUserId } from "@/lib/auth/session";
import { calendarConnectionSchema } from "@/lib/validators/calendar";
import { successResponse, errorResponse } from "@/lib/api-response";

export async function POST(request: NextRequest) {
  try {
    const userId = await getCurrentUserId();
    if (!userId) return errorResponse("Demo mode — calendar connections are view-only", 403);

    const body = await request.json();
    const payload = calendarConnectionSchema.parse(body);

    const connection = await prisma.calendarConnection.create({
      data: { userId, ...payload }
    });

    return successResponse(
      { ...connection, connectedAt: connection.connectedAt.toISOString() },
      { status: 201 }
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return errorResponse(message);
  }
}
