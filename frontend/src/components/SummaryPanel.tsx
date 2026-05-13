"use client";

import { useState, useCallback } from "react";
import { ChevronDown, ChevronUp, Loader2, Sparkles } from "lucide-react";
import { documentsApi } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { cn, getErrorMessage } from "@/lib/utils";
import type { Document } from "@/lib/types";

interface Props {
  document: Document;
}

export function SummaryPanel({ document }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [summary, setSummary] = useState<string | null>(document.summary);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const upsertDocument = useAppStore((s) => s.upsertDocument);

  const loadSummary = useCallback(async () => {
    if (summary) { setIsOpen((v) => !v); return; }
    if (!isOpen) {
      setIsOpen(true);
      setIsLoading(true);
      setError(null);
      try {
        const { data } = await documentsApi.summary(document.id);
        setSummary(data.summary);
        upsertDocument({ ...document, summary: data.summary });
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    } else {
      setIsOpen(false);
    }
  }, [summary, isOpen, document, upsertDocument]);

  return (
    <div className="flex-shrink-0 border-b border-surface-warm bg-white">
      <button
        onClick={loadSummary}
        className="w-full flex items-center gap-2 px-6 py-2.5 hover:bg-surface/60 transition-colors text-left"
      >
        <Sparkles size={13} className="text-accent flex-shrink-0" />
        <span className="text-xs font-semibold text-ink flex-1">AI Summary</span>
        {isLoading && <Loader2 size={12} className="text-accent animate-spin" />}
        {!isLoading && (isOpen ? <ChevronUp size={13} className="text-ink/30" /> : <ChevronDown size={13} className="text-ink/30" />)}
      </button>

      {isOpen && (
        <div className="px-6 pb-4 animate-fade-up">
          {isLoading && (
            <div className="space-y-2 py-2">
              {[80, 95, 70, 88].map((w, i) => (
                <div key={i} className="h-3 shimmer rounded-full" style={{ width: `${w}%` }} />
              ))}
            </div>
          )}
          {error && (
            <p className="text-xs text-red-400 py-2">{error}</p>
          )}
          {summary && !isLoading && (
            <p className="text-sm text-ink/70 leading-relaxed font-body border-l-2 border-accent/30 pl-3">
              {summary}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
