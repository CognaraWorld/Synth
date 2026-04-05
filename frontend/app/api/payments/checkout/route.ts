import { NextRequest } from "next/server";
import { z } from "zod";
import { successResponse, errorResponse } from "@/lib/api-response";
import { backendPost } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";

const checkoutSchema = z.object({
  pack_id: z.enum(["pack_5", "pack_20", "pack_50"]),
});

export async function POST(request: NextRequest) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const raw = await request.json();
    const body = checkoutSchema.safeParse(raw);
    if (!body.success) {
      return errorResponse("Invalid pack_id. Must be pack_5, pack_20, or pack_50.", 400);
    }

    const checkout = await backendPost("/api/payments/create-checkout", body.data, token);
    return successResponse(checkout);
  } catch (error) {
    return backendErrorResponse(error, "Failed to create checkout");
  }
}
