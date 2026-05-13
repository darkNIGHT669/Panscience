import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatTimestamp(seconds: number): string {
  return formatDuration(seconds);
}

export function fileTypeIcon(fileType: string): string {
  switch (fileType) {
    case "pdf": return "📄";
    case "audio": return "🎵";
    case "video": return "🎬";
    default: return "📁";
  }
}

export function fileTypeLabel(fileType: string): string {
  switch (fileType) {
    case "pdf": return "PDF Document";
    case "audio": return "Audio File";
    case "video": return "Video File";
    default: return "File";
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null) {
    const axiosError = error as { response?: { data?: { detail?: string } } };
    if (axiosError.response?.data?.detail) return axiosError.response.data.detail;
  }
  return "An unexpected error occurred";
}
