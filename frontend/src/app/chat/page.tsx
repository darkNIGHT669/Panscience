"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/store/appStore";
import { documentsApi } from "@/lib/api";
import { FileList } from "@/components/FileList";
import { ChatWindow } from "@/components/ChatWindow";
import { MediaPlayer } from "@/components/MediaPlayer";
import { FileUploader } from "@/components/FileUploader";
import { SummaryPanel } from "@/components/SummaryPanel";

export default function ChatPage() {
  const { user, setDocuments, activeDocument } = useAppStore();
  const router = useRouter();

  // Auth guard
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) router.replace("/auth/login");
  }, [router]);

  // Load documents on mount
  useEffect(() => {
    documentsApi
      .list()
      .then(({ data }) => setDocuments(data.documents))
      .catch(() => {});
  }, [setDocuments]);

  const showPlayer =
    activeDocument && (activeDocument.file_type === "audio" || activeDocument.file_type === "video");

  return (
    <div className="h-screen flex overflow-hidden bg-surface grain">
      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <aside className="w-72 flex-shrink-0 flex flex-col border-r border-surface-warm bg-surface-card">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-surface-warm flex items-center justify-between">
          <span className="font-display text-lg font-bold text-ink tracking-tight">
            Pan<span className="text-accent">Science</span>
          </span>
          {user && (
            <button
              onClick={() => useAppStore.getState().logout()}
              className="text-xs text-ink/30 hover:text-accent transition-colors font-mono"
            >
              sign out
            </button>
          )}
        </div>

        {/* Upload zone */}
        <div className="px-4 py-4 border-b border-surface-warm">
          <FileUploader />
        </div>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto">
          <FileList />
        </div>
      </aside>

      {/* ── Main content ──────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Media player — shown above chat when audio/video is active */}
        {showPlayer && (
          <div className="flex-shrink-0 border-b border-surface-warm bg-ink">
            <MediaPlayer document={activeDocument} />
          </div>
        )}

        {/* Summary panel (collapsible) */}
        {activeDocument && activeDocument.status === "ready" && (
          <SummaryPanel document={activeDocument} />
        )}

        {/* Chat window */}
        <div className="flex-1 overflow-hidden">
          <ChatWindow />
        </div>
      </main>
    </div>
  );
}
