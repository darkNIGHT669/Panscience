"use client";

import dynamic from "next/dynamic";
import { Play, Pause, Volume2 } from "lucide-react";
import { useMediaPlayer } from "@/hooks/useMediaPlayer";
import { formatDuration } from "@/lib/utils";
import type { Document } from "@/lib/types";

// react-player must be loaded client-side only (no SSR)
const ReactPlayer = dynamic(() => import("react-player/lazy"), { ssr: false });

interface Props {
  document: Document;
}

export function MediaPlayer({ document }: Props) {
  const {
    playerRef,
    isPlaying,
    setIsPlaying,
    currentTime,
    duration,
    togglePlay,
    handleProgress,
    handleDuration,
    handleSeek,
  } = useMediaPlayer();

  const fileUrl = `/api/documents/${document.id}/stream`; // served via backend
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-4 px-6 py-3 bg-ink">
      {/* Hidden react-player */}
      <div className="sr-only">
        <ReactPlayer
          ref={playerRef as React.Ref<typeof ReactPlayer>}
          url={fileUrl}
          playing={isPlaying}
          onProgress={handleProgress}
          onDuration={handleDuration}
          width="1px"
          height="1px"
          config={{
            file: { attributes: { crossOrigin: "use-credentials" } },
          }}
        />
      </div>

      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        className="w-8 h-8 rounded-lg bg-white/10 hover:bg-accent flex items-center justify-center
          text-white transition-all flex-shrink-0"
      >
        {isPlaying ? <Pause size={14} /> : <Play size={14} />}
      </button>

      {/* File info */}
      <div className="min-w-0 flex-shrink-0">
        <p className="text-[11px] font-medium text-white truncate max-w-[140px]">
          {document.original_filename}
        </p>
        <p className="text-[10px] text-white/40 font-mono capitalize">{document.file_type}</p>
      </div>

      {/* Progress bar */}
      <div className="flex-1 flex items-center gap-3">
        <span className="text-[10px] text-white/40 font-mono w-10 text-right flex-shrink-0">
          {formatDuration(currentTime)}
        </span>
        <div
          className="flex-1 h-1 bg-white/10 rounded-full cursor-pointer relative group"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - rect.left) / rect.width;
            handleSeek(ratio * duration);
          }}
        >
          <div
            className="h-full bg-accent rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full
              opacity-0 group-hover:opacity-100 transition-opacity shadow-md -translate-x-1/2"
            style={{ left: `${progress}%` }}
          />
        </div>
        <span className="text-[10px] text-white/40 font-mono w-10 flex-shrink-0">
          {formatDuration(duration)}
        </span>
      </div>

      <Volume2 size={14} className="text-white/30 flex-shrink-0" />
    </div>
  );
}
