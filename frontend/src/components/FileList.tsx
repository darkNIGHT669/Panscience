"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { Trash2, FileText, Music, Video, Loader2, AlertCircle, CheckCircle2, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { documentsApi, chatApi } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { cn, formatBytes } from "@/lib/utils";
import type { Document } from "@/lib/types";

const FILE_ICONS = {
  pdf: FileText,
  audio: Music,
  video: Video,
} as const;

const STATUS_COLORS = {
  ready: "text-sage",
  processing: "text-amber-qs",
  error: "text-red-400",
} as const;

export function FileList() {
  const { documents, removeDocument, setActiveSession, activeDocument } = useAppStore();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);

  const handleSelect = async (doc: Document) => {
    if (doc.status !== "ready") return;
    setOpeningId(doc.id);
    try {
      const { data: session } = await chatApi.createSession(doc.id);
      setActiveSession(session, doc);
    } catch {
      toast.error("Failed to open chat session");
    } finally {
      setOpeningId(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeletingId(id);
    try {
      await documentsApi.delete(id);
      removeDocument(id);
      toast.success("Document deleted");
    } catch {
      toast.error("Failed to delete document");
    } finally {
      setDeletingId(null);
    }
  };

  if (documents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 px-4 text-center">
        <div className="w-10 h-10 rounded-lg bg-surface flex items-center justify-center mb-3">
          <FileText size={18} className="text-ink/20" />
        </div>
        <p className="text-xs text-ink/30 font-body leading-relaxed">
          Upload a PDF, audio, or video file to get started
        </p>
      </div>
    );
  }

  return (
    <div className="px-3 py-3 space-y-1 stagger">
      <p className="text-[10px] font-mono text-ink/30 uppercase tracking-widest px-2 mb-3">
        Documents · {documents.length}
      </p>
      {documents.map((doc) => {
        const Icon = FILE_ICONS[doc.file_type] ?? FileText;
        const isActive = activeDocument?.id === doc.id;
        const isOpening = openingId === doc.id;
        const isDeleting = deletingId === doc.id;

        return (
          <div
            key={doc.id}
            onClick={() => handleSelect(doc)}
            className={cn(
              "group flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer transition-all",
              isActive ? "bg-accent/10 border border-accent/20" : "hover:bg-surface-warm border border-transparent",
              doc.status !== "ready" && "opacity-60 cursor-default"
            )}
          >
            {/* Icon */}
            <div className={cn(
              "w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 transition-colors",
              isActive ? "bg-accent text-white" : "bg-surface text-ink/50"
            )}>
              <Icon size={13} />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-ink truncate leading-tight">
                {doc.original_filename}
              </p>
              <div className="flex items-center gap-1.5 mt-0.5">
                {doc.status === "processing" && (
                  <Loader2 size={9} className="text-amber-qs animate-spin" />
                )}
                {doc.status === "ready" && (
                  <CheckCircle2 size={9} className="text-sage" />
                )}
                {doc.status === "error" && (
                  <AlertCircle size={9} className="text-red-400" />
                )}
                <span className={cn("text-[10px] font-mono capitalize", STATUS_COLORS[doc.status])}>
                  {doc.status}
                </span>
                <span className="text-[10px] text-ink/20">·</span>
                <span className="text-[10px] text-ink/30 font-mono">
                  {formatBytes(doc.file_size_bytes)}
                </span>
              </div>
            </div>

            {/* Actions */}
            {isOpening ? (
              <Loader2 size={13} className="text-accent animate-spin flex-shrink-0" />
            ) : isDeleting ? (
              <Loader2 size={13} className="text-red-400 animate-spin flex-shrink-0" />
            ) : (
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => handleDelete(e, doc.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 text-ink/30 hover:text-red-400 transition-all"
                  title="Delete"
                >
                  <Trash2 size={11} />
                </button>
                {isActive && <ChevronRight size={12} className="text-accent" />}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
