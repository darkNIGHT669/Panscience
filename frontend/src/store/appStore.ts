import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatSession, Document, UploadProgress, User } from "@/lib/types";

interface AppState {
  // ─── Auth ─────────────────────────────────────────────────────────────────
  user: User | null;
  token: string | null;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  logout: () => void;

  // ─── Documents ────────────────────────────────────────────────────────────
  documents: Document[];
  setDocuments: (docs: Document[]) => void;
  upsertDocument: (doc: Document) => void;
  removeDocument: (id: string) => void;

  // ─── Upload queue ─────────────────────────────────────────────────────────
  uploads: UploadProgress[];
  addUpload: (up: UploadProgress) => void;
  updateUpload: (filename: string, patch: Partial<UploadProgress>) => void;
  removeUpload: (filename: string) => void;

  // ─── Active session ───────────────────────────────────────────────────────
  activeSession: ChatSession | null;
  activeDocument: Document | null;
  setActiveSession: (session: ChatSession | null, doc: Document | null) => void;

  // ─── Media player seek event ──────────────────────────────────────────────
  seekTo: number | null;
  triggerSeek: (seconds: number) => void;
  clearSeek: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      user: null,
      token: null,
      setUser: (user) => set({ user }),
      setToken: (token) => set({ token }),
      logout: () => {
        if (typeof window !== "undefined") localStorage.removeItem("access_token");
        set({ user: null, token: null, activeSession: null, activeDocument: null });
      },

      // Documents
      documents: [],
      setDocuments: (documents) => set({ documents }),
      upsertDocument: (doc) =>
        set((s) => ({
          documents: s.documents.some((d) => d.id === doc.id)
            ? s.documents.map((d) => (d.id === doc.id ? doc : d))
            : [doc, ...s.documents],
        })),
      removeDocument: (id) =>
        set((s) => ({ documents: s.documents.filter((d) => d.id !== id) })),

      // Uploads
      uploads: [],
      addUpload: (up) => set((s) => ({ uploads: [...s.uploads, up] })),
      updateUpload: (filename, patch) =>
        set((s) => ({
          uploads: s.uploads.map((u) =>
            u.file_name === filename ? { ...u, ...patch } : u
          ),
        })),
      removeUpload: (filename) =>
        set((s) => ({ uploads: s.uploads.filter((u) => u.file_name !== filename) })),

      // Active session
      activeSession: null,
      activeDocument: null,
      setActiveSession: (session, doc) =>
        set({ activeSession: session, activeDocument: doc }),

      // Media seek
      seekTo: null,
      triggerSeek: (seconds) => set({ seekTo: seconds }),
      clearSeek: () => set({ seekTo: null }),
    }),
    {
      name: "panscience-store",
      partialize: (s) => ({ user: s.user, token: s.token }),
    }
  )
);
