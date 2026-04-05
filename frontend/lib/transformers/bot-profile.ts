import type { BotProfileDTO, GlobalDocumentDTO, ResponseMode, VoiceOption } from "@/types";

export interface BackendBotProfileResponse {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  mode: string;
  persona_id: string;
  voice: string;
  response_mode: string;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackendDocumentResponse {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  parsed: boolean;
  chunk_count: number;
  doc_summary?: string | null;
  created_at: string;
}

type DashboardBotProfileInput = {
  name: string;
  persona: string;
  voice: VoiceOption;
  responseMode: ResponseMode;
};

type BackendBotProfileUpsertPayload = {
  name: string;
  description: string;
  mode: "general";
  persona_id: "general";
  voice: "male" | "female";
  response_mode: "name_only" | "proactive";
};

const FILE_TYPE_BY_EXTENSION: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  txt: "text/plain"
};

function mapVoice(voice: string | null | undefined): VoiceOption {
  return voice?.toLowerCase() === "male" ? "MALE" : "FEMALE";
}

function mapResponseMode(mode: string | null | undefined): ResponseMode {
  return mode === "proactive" ? "PROACTIVE" : "WAKE_WORD_ONLY";
}

function mapDocumentType(fileType: string | null | undefined) {
  const normalized = (fileType ?? "").toLowerCase();
  return FILE_TYPE_BY_EXTENSION[normalized] ?? (normalized || "application/octet-stream");
}

function stripExtension(filename: string) {
  return filename.replace(/\.[^./\\]+$/, "");
}

export function transformDocument(backend: BackendDocumentResponse): GlobalDocumentDTO {
  return {
    id: String(backend.id),
    name: stripExtension(backend.filename),
    fileName: backend.filename,
    fileType: mapDocumentType(backend.file_type),
    fileSize: backend.file_size ?? 0,
    fileUrl: "",
    createdAt: backend.created_at
  };
}

export function transformBotProfile(backend: BackendBotProfileResponse): BotProfileDTO {
  return {
    id: String(backend.id),
    name: backend.name,
    persona: backend.description,
    voice: mapVoice(backend.voice),
    responseMode: mapResponseMode(backend.response_mode),
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
    documents: []
  };
}

export function transformBotProfileForUpsert(
  input: DashboardBotProfileInput
): BackendBotProfileUpsertPayload {
  return {
    name: input.name,
    description: input.persona,
    mode: "general",
    persona_id: "general",
    voice: input.voice.toLowerCase() as "male" | "female",
    response_mode: input.responseMode === "PROACTIVE" ? "proactive" : "name_only"
  };
}
