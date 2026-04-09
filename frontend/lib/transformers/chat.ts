export interface CitationReference {
  type: "transcript" | "document";
  timestamp?: string;
  filename?: string;
  page?: number;
  raw: string;
}

export interface ToolCallInfo {
  tool_name: string;
  input: Record<string, unknown>;
  output_summary: string;
}

export interface BackendChatMessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations?: CitationReference[] | null;
  tool_calls?: ToolCallInfo[] | null;
}

export interface BackendChatResponse {
  user_message: BackendChatMessageResponse;
  assistant_message: BackendChatMessageResponse;
  follow_ups?: string[] | null;
}

export interface BackendChatHistoryResponse {
  messages: BackendChatMessageResponse[];
  meeting_id: string;
  total: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  citations?: CitationReference[] | null;
  toolCalls?: ToolCallInfo[] | null;
}

export function transformChatMessage(backend: BackendChatMessageResponse): ChatMessage {
  return {
    id: String(backend.id),
    role: backend.role,
    content: backend.content,
    createdAt: backend.created_at,
    citations: backend.citations ?? null,
    toolCalls: backend.tool_calls ?? null,
  };
}
