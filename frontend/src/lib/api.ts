import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type {
  ChatSession,
  Document,
  DocumentListResponse,
  Message,
  TimestampResponse,
  TokenResponse,
  User,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// ─── JWT Interceptor ──────────────────────────────────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/auth/login";
      }
    }
    return Promise.reject(error);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (email: string, password: string, full_name?: string) =>
    apiClient.post<User>("/auth/register", { email, password, full_name }),

  login: async (email: string, password: string): Promise<string> => {
    const { data } = await apiClient.post<TokenResponse>("/auth/login", {
      email,
      password,
    });
    localStorage.setItem("access_token", data.access_token);
    return data.access_token;
  },

  me: () => apiClient.get<User>("/auth/me"),

  logout: () => {
    localStorage.removeItem("access_token");
    window.location.href = "/auth/login";
  },
};

// ─── Documents ────────────────────────────────────────────────────────────────
export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.post<Document>("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100));
      },
    });
  },

  list: () => apiClient.get<DocumentListResponse>("/documents/"),

  get: (id: string) => apiClient.get<Document>(`/documents/${id}`),

  delete: (id: string) => apiClient.delete(`/documents/${id}`),

  summary: (id: string) =>
    apiClient.get<{ document_id: string; summary: string; cached: boolean }>(
      `/documents/${id}/summary`
    ),

  timestamps: (id: string, topic: string) =>
    apiClient.get<TimestampResponse>(`/documents/${id}/timestamps`, {
      params: { topic },
    }),
};

// ─── Chat ─────────────────────────────────────────────────────────────────────
export const chatApi = {
  createSession: (document_id: string, title?: string) =>
    apiClient.post<ChatSession>("/chat/sessions", { document_id, title }),

  listSessions: () => apiClient.get<ChatSession[]>("/chat/sessions"),

  deleteSession: (id: string) => apiClient.delete(`/chat/sessions/${id}`),

  getMessages: (session_id: string) =>
    apiClient.get<Message[]>(`/chat/sessions/${session_id}/messages`),

  /**
   * Returns a ReadableStream for SSE token streaming.
   * Caller iterates with an async reader.
   */
  streamMessage: async (session_id: string, question: string): Promise<ReadableStream<string>> => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

    const response = await fetch(`${BASE_URL}/chat/sessions/${session_id}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) throw new Error(`Chat error: ${response.status}`);
    if (!response.body) throw new Error("No response body");

    return response.body.pipeThrough(new TextDecoderStream());
  },
};

// ─── Polling helper for document status ───────────────────────────────────────
export async function pollDocumentReady(
  id: string,
  onUpdate: (doc: Document) => void,
  intervalMs = 2000,
  maxAttempts = 60
): Promise<Document> {
  for (let i = 0; i < maxAttempts; i++) {
    const { data } = await documentsApi.get(id);
    onUpdate(data);
    if (data.status === "ready" || data.status === "error") return data;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("Document processing timed out");
}
