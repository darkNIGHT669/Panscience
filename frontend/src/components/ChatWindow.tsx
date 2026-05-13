"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Square, Sparkles, MessageSquare } from "lucide-react";
import { useAppStore } from "@/store/appStore";
import { useChat } from "@/hooks/useChat";
import { MessageBubble } from "@/components/MessageBubble";
import { cn } from "@/lib/utils";

export function ChatWindow() {
  const { activeSession, activeDocument } = useAppStore();
  const { messages, isStreaming, error, sendMessage, stopStream, jumpToTimestamp } = useChat(
    activeSession?.id ?? null
  );
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput("");
    await sendMessage(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Empty states
  if (!activeSession) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-5">
          <MessageSquare size={28} className="text-accent" />
        </div>
        <h2 className="font-display text-2xl font-bold text-ink mb-3">
          Select a document to begin
        </h2>
        <p className="text-ink/40 text-sm max-w-xs leading-relaxed font-body">
          Choose a file from the sidebar, then ask questions, get summaries, or jump to specific timestamps.
        </p>

        <div className="mt-10 grid grid-cols-3 gap-3 w-full max-w-md">
          {[
            { icon: "📄", label: "Summarize PDF", hint: "Upload any PDF" },
            { icon: "🎵", label: "Audio Q&A", hint: "Ask about audio" },
            { icon: "🎬", label: "Video timestamps", hint: "Find key moments" },
          ].map((card) => (
            <div key={card.label} className="bg-white rounded-xl p-4 border border-surface-warm text-left shadow-card">
              <span className="text-2xl">{card.icon}</span>
              <p className="text-xs font-semibold text-ink mt-2 leading-tight">{card.label}</p>
              <p className="text-[11px] text-ink/40 mt-0.5">{card.hint}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-surface-warm bg-surface-card flex items-center gap-3">
        <div className="w-6 h-6 rounded-md bg-accent/10 flex items-center justify-center">
          <Sparkles size={12} className="text-accent" />
        </div>
        <div>
          <p className="text-xs font-semibold text-ink leading-tight">
            {activeDocument?.original_filename}
          </p>
          <p className="text-[10px] text-ink/40 font-mono capitalize">
            {activeDocument?.file_type} · AI Q&A active
          </p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center animate-fade-in">
            <p className="text-ink/30 text-sm font-body">Ask anything about this document…</p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              {[
                "Summarize the key points",
                "What are the main conclusions?",
                "Find mentions of methodology",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => { setInput(suggestion); textareaRef.current?.focus(); }}
                  className="text-xs px-3 py-1.5 bg-white border border-surface-warm rounded-full
                    text-ink/60 hover:text-accent hover:border-accent/30 transition-all font-body"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onJumpToTimestamp={jumpToTimestamp} />
        ))}

        {error && (
          <div className="flex justify-center">
            <div className="px-4 py-2 bg-red-50 border border-red-100 rounded-lg text-xs text-red-500">
              {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 px-6 py-4 border-t border-surface-warm bg-surface-card">
        <div className={cn(
          "flex items-end gap-3 bg-white border rounded-2xl px-4 py-3 transition-all shadow-card",
          "focus-within:ring-2 focus-within:ring-accent/30 focus-within:border-accent/40"
        )}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question… (Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-ink placeholder:text-ink/30
              focus:outline-none font-body leading-relaxed"
          />
          <button
            onClick={isStreaming ? stopStream : handleSend}
            disabled={!isStreaming && !input.trim()}
            className={cn(
              "flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all",
              isStreaming
                ? "bg-red-500 hover:bg-red-600 text-white"
                : input.trim()
                ? "bg-accent hover:bg-accent-hover text-white shadow-sm"
                : "bg-surface text-ink/20 cursor-not-allowed"
            )}
          >
            {isStreaming ? <Square size={13} /> : <Send size={13} />}
          </button>
        </div>
        <p className="text-[10px] text-ink/20 mt-2 text-center font-mono">
          AI may make mistakes · Always verify critical information
        </p>
      </div>
    </div>
  );
}
