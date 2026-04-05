import { NextRequest } from "next/server";
import { successResponse, errorResponse } from "@/lib/api-response";
import { backendGet, backendPostForm } from "@/lib/backend-client";
import { backendErrorResponse, notAuthenticatedResponse, requireBackendToken } from "@/lib/backend-proxy";
import {
  type BackendBotProfileResponse,
  type BackendDocumentResponse,
  transformDocument
} from "@/lib/transformers/bot-profile";

export async function POST(request: NextRequest) {
  const token = await requireBackendToken();
  if (!token) {
    return notAuthenticatedResponse();
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file") as File | null;

    if (!file) {
      return errorResponse("No file provided");
    }

    const bot = await backendGet<BackendBotProfileResponse>("/api/bot/profile", token);
    const payload = new FormData();
    payload.append("file", file);

    const document = await backendPostForm<BackendDocumentResponse>(`/api/documents/upload/${bot.id}`, payload, token);
    return successResponse(transformDocument(document), { status: 201 });
  } catch (error) {
    return backendErrorResponse(error, "Upload failed");
  }
}
