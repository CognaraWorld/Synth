import axios from "axios";

function resolveApiBaseUrl(): string {
  const fallbackUrl = "http://localhost:8000/api";
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!envUrl) return fallbackUrl;

  const withoutTrailingSlash = envUrl.replace(/\/+$/, "");
  try {
    const parsed = new URL(withoutTrailingSlash);
    const normalizedPath = (parsed.pathname || "/").replace(/\/+$/, "");
    const pathWithApi =
      normalizedPath === "" || normalizedPath === "/"
        ? "/api"
        : normalizedPath.endsWith("/api")
          ? normalizedPath
          : `${normalizedPath}/api`;
    return `${parsed.origin}${pathWithApi}`;
  } catch {
    // Bare host:port (e.g. "localhost:8000") — URL() requires a scheme
    if (!withoutTrailingSlash.includes("://")) {
      try {
        const parsed = new URL(`http://${withoutTrailingSlash}`);
        const normalizedPath = (parsed.pathname || "/").replace(/\/+$/, "");
        const pathWithApi =
          normalizedPath === "" || normalizedPath === "/"
            ? "/api"
            : normalizedPath.endsWith("/api")
              ? normalizedPath
              : `${normalizedPath}/api`;
        return `${parsed.origin}${pathWithApi}`;
      } catch {
        // fall through to fallback
      }
    }
    return fallbackUrl;
  }
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("auth_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth
export async function login(email: string, password: string) {
  const { data } = await api.post("/auth/login", { email, password });
  return data;
}

export async function register(
  name: string,
  email: string,
  password: string
) {
  const { data } = await api.post("/auth/register", {
    name,
    email,
    password,
    provider: "email",
  });
  return data;
}

export async function getMe() {
  const { data } = await api.get("/auth/me");
  return data;
}

// Agents
export type PersonaId =
  | "general"
  | "strategist"
  | "analyst"
  | "challenger"
  | "facilitator";

export async function getAgents() {
  const { data } = await api.get("/agents");
  return data;
}

export async function getAgent(id: string) {
  const { data } = await api.get(`/agents/${id}`);
  return data;
}

export async function createAgent(agent: {
  name: string;
  description: string;
  mode: "general";
  persona_id?: PersonaId;
  response_mode?: "name_only" | "proactive";
}) {
  const { data } = await api.post("/agents", agent);
  return data;
}

export async function deleteAgent(id: string) {
  const { data } = await api.delete(`/agents/${id}`);
  return data;
}

// Meetings
export async function getMeetings() {
  const { data } = await api.get("/meetings");
  return data;
}

export async function getMeeting(id: string) {
  const { data } = await api.get(`/meetings/${id}`);
  return data;
}

export async function createMeeting(meeting: {
  meeting_link: string;
  agent_id: string;
}) {
  const { data } = await api.post("/meetings", meeting);
  return data;
}

export async function stopMeeting(id: string) {
  const { data } = await api.post(`/meetings/${id}/stop`);
  return data;
}

// Documents
export async function uploadDocument(agentId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post(`/documents/upload/${agentId}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getDocuments(agentId: string) {
  const { data } = await api.get(`/documents/${agentId}`);
  return data;
}

export async function deleteDocument(id: string) {
  const { data } = await api.delete(`/documents/${id}`);
  return data;
}

export default api;
