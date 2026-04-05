export interface BackendChatMessageResponse {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface BackendChatResponse {
  user_message: BackendChatMessageResponse;
  assistant_message: BackendChatMessageResponse;
}

export interface BackendChatHistoryResponse {
  messages: BackendChatMessageResponse[];
  meeting_id: string;
  total: number;
  page: number;
  per_page: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export function transformChatMessage(backend: BackendChatMessageResponse): ChatMessage {
  return {
    id: String(backend.id),
    role: backend.role,
    content: backend.content,
    createdAt: backend.created_at,
  };
}
