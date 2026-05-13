"use client";

import { useState } from "react";
import { Play, FileText, Clock } from "lucide-react";
import { cn, formatTimestamp } from "@/lib/utils";
import type { StreamingMessage, Citation } from "@/lib/types";

interface Props {
  message: StreamingMessage;
  onJumpToTimestamp: (seconds: number) => void;
}

export function MessageBubble({ message, onJumpToTimestamp }: Props) {
  const isUser = message.role === "user";
  const [showCitations, setShowCitations] = useState(false);
  const hasCitations = message.citations && message.citations.length > 0;
  const hasTimestamps = message.citations?.some((c) => c.start_time !== null);

  return (
    <div className={cn("flex gap-3 animate-fade-up", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className={cn(
        "w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold font-display mt-0.5",
        isUser ? "bg-ink text-white" : "bg-accent/10 text-accent"
      )}>
        {isUser ? "U" : "AI"}
      </div>

      {/* Bubble */}
      <div className={cn("max-w-[80%] space-y-2", isUser && "items-end flex flex-col")}>
        <div className={cn(
          "rounded-2xl px-4 py-3 text-sm leading-relaxed font-body",
          isUser
            ? "bg-ink text-white rounded-tr-sm"
            : "bg-white border border-surface-warm shadow-card rounded-tl-sm text-ink"
        )}>
          {message.isStreaming && !message.content ? (
            <div className="flex gap-1 items-center h-5">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-accent/40 animate-pulse2"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          ) : (
            <span className={cn(
              "whitespace-pre-wrap",
              message.isStreaming && message.content && "typing-cursor"
            )}>
              {message.content}
            </span>
          )}
        </div>

        {/* Citations & Actions */}
        {!isUser && hasCitations && !message.isStreaming && (
          <div className="space-y-1">
            {/* Toggle citations */}
            <button
              onClick={() => setShowCitations((v) => !v)}
              className="flex items-center gap-1.5 text-[11px] text-ink/40 hover:text-accent transition-colors"
            >
              <FileText size={10} />
              <span>
                {message.citations!.length} source{message.citations!.length !== 1 ? "s" : ""}
              </span>
              <span className="text-ink/20">{showCitations ? "▲" : "▼"}</span>
            </button>

            {/* Timestamp play buttons — always visible if present */}
            {hasTimestamps && (
              <div className="flex flex-wrap gap-1.5">
                {message.citations!
                  .filter((c) => c.start_time !== null)
                  .map((c, i) => (
                    <TimestampButton
                      key={c.chunk_id}
                      citation={c}
                      index={i}
                      onPlay={() => onJumpToTimestamp(c.start_time!)}
                    />
                  ))}
              </div>
            )}

            {/* Citation snippets */}
            {showCitations && (
              <div className="space-y-1.5 mt-1">
                {message.citations!.map((c, i) => (
                  <CitationCard key={c.chunk_id} citation={c} index={i} onPlay={onJumpToTimestamp} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TimestampButton({
  citation,
  index,
  onPlay,
}: {
  citation: Citation;
  index: number;
  onPlay: () => void;
}) {
  return (
    <button
      onClick={onPlay}
      className="flex items-center gap-1.5 px-2.5 py-1 bg-ink text-white rounded-full text-[11px]
        font-mono hover:bg-accent transition-all group"
    >
      <Play size={9} className="group-hover:scale-110 transition-transform" />
      {formatTimestamp(citation.start_time!)}
      {citation.end_time && (
        <span className="text-white/40">
          → {formatTimestamp(citation.end_time)}
        </span>
      )}
    </button>
  );
}

function CitationCard({
  citation,
  index,
  onPlay,
}: {
  citation: Citation;
  index: number;
  onPlay: (seconds: number) => void;
}) {
  return (
    <div className="bg-surface rounded-lg p-2.5 border border-surface-warm text-[11px] font-body">
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-ink/30">Source {index + 1}</span>
        <div className="flex items-center gap-2 text-ink/40">
          {citation.page_num && (
            <span className="flex items-center gap-1">
              <FileText size={9} />
              p.{citation.page_num}
            </span>
          )}
          {citation.start_time !== null && (
            <button
              onClick={() => onPlay(citation.start_time!)}
              className="flex items-center gap-1 hover:text-accent transition-colors"
            >
              <Clock size={9} />
              {formatTimestamp(citation.start_time)}
            </button>
          )}
        </div>
      </div>
      <p className="text-ink/60 leading-relaxed line-clamp-3">{citation.text_snippet}</p>
    </div>
  );
}
