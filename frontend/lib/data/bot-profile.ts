import { getBackendToken } from "@/lib/auth/session";
import { backendGet, backendPut } from "@/lib/backend-client";
import { sampleBotProfile } from "@/lib/sample-data";
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
  if (!token) return sampleBotProfile;

  try {
    return await loadBotProfileWithDocuments(token);
  } catch (err) {
    console.error("[bot-profile] getBotProfile failed:", err);
    return sampleBotProfile;
  }
}

export async function upsertBotProfile(input: unknown) {
  const payload = botProfileSchema.parse(input);
  const token = await getBackendToken();

  if (!token) {
    return { ...sampleBotProfile, ...payload, updatedAt: new Date().toISOString() };
  }

  try {
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
  } catch (err) {
    console.error("[bot-profile] upsertBotProfile failed:", err);
    return { ...sampleBotProfile, ...payload, updatedAt: new Date().toISOString() };
  }
}
