// ─── Auth ─────────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ─── Documents ────────────────────────────────────────────────────────────────
export type FileType = "pdf" | "audio" | "video";
export type DocumentStatus = "processing" | "ready" | "error";

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_type: FileType;
  mime_type: string;
  file_size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  summary: string | null;
  duration_seconds: number | null;
  page_count: number | null;
  created_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────
export interface ChatSession {
  id: string;
  document_id: string | null;
  title: string | null;
  created_at: string;
}

export interface Citation {
  chunk_id: string;
  page_num: number | null;
  start_time: number | null;
  end_time: number | null;
  text_snippet: string;
}

export interface Message {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[] | null;
  created_at: string;
}

// ─── SSE Stream ───────────────────────────────────────────────────────────────
export type SSEEventType = "token" | "citations" | "done" | "error";

export interface SSEEvent {
  type: SSEEventType;
  data: string | Citation[] | null;
}

// ─── Timestamps ───────────────────────────────────────────────────────────────
export interface TimestampEntry {
  chunk_id: string;
  start_time: number;
  end_time: number;
  text: string;
  relevance_score: number | null;
}

export interface TimestampResponse {
  document_id: string;
  topic: string;
  results: TimestampEntry[];
}

// ─── UI State ─────────────────────────────────────────────────────────────────
export interface UploadProgress {
  file_name: string;
  progress: number; // 0–100
  status: "uploading" | "processing" | "done" | "error";
  document_id?: string;
  error?: string;
}

export interface StreamingMessage extends Omit<Message, "id" | "session_id" | "created_at"> {
  id: string;
  isStreaming?: boolean;
}
