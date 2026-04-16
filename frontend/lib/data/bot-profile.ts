import { getBackendToken } from "@/lib/auth/session";
import { backendGet, backendPut } from "@/lib/backend-client";
import {
  type BackendBotProfileResponse,
  type BackendDocumentResponse,
  transformBotProfile,
  transformBotProfileForUpsert,
  transformDocument
} from "@/lib/transformers/bot-profile";
import { botProfileSchema } from "@/lib/validators/bot";

async function loadBotProfileWithDocuments(token: string) {
  const bot = await backendGet<BackendBotProfileResponse>("/api/bot/profile", token);
  const documents = await backendGet<BackendDocumentResponse[]>(`/api/documents/${bot.id}`, token).catch(
    () => []
  );

  return {
    ...transformBotProfile(bot),
    documents: documents.map(transformDocument)
  };
}

export async function getBotProfile() {
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  return loadBotProfileWithDocuments(token);
}

export async function upsertBotProfile(input: unknown) {
  const payload = botProfileSchema.parse(input);
  const token = await getBackendToken();
  if (!token) {
    throw new Error("Not authenticated");
  }
  const bot = await backendPut<BackendBotProfileResponse>(
    "/api/bot/profile",
    transformBotProfileForUpsert(payload),
    token
  );
  const documents = await backendGet<BackendDocumentResponse[]>(`/api/documents/${bot.id}`, token).catch(
    () => []
  );
  return {
    ...transformBotProfile(bot),
    documents: documents.map(transformDocument)
  };
}
