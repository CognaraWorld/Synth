import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
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
      window.location.href = "/";
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
  const { data } = await api.post("/auth/register", { name, email, password });
  return data;
}

// Agents
export async function getAgents() {
  const { data } = await api.get("/agents");
  return data;
}

export async function createAgent(agent: {
  name: string;
  description: string;
  mode: "general" | "custom";
}) {
  const { data } = await api.post("/agents", agent);
  return data;
}

// Meetings
export async function getMeetings() {
  const { data } = await api.get("/meetings");
  return data;
}

export async function createMeeting(meeting: {
  platform: string;
  meeting_url: string;
  agent_id: string;
}) {
  const { data } = await api.post("/meetings", meeting);
  return data;
}

// Documents
export async function uploadDocument(agentId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post(`/agents/${agentId}/documents`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export default api;
