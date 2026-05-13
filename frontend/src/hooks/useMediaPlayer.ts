"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAppStore } from "@/store/appStore";

export function useMediaPlayer() {
  const playerRef = useRef<{ seekTo: (seconds: number, type?: string) => void } | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const { seekTo, clearSeek } = useAppStore();

  // React to store-level seek events (triggered by chat citations)
  useEffect(() => {
    if (seekTo !== null && playerRef.current) {
      playerRef.current.seekTo(seekTo, "seconds");
      setIsPlaying(true);
      clearSeek();
    }
  }, [seekTo, clearSeek]);

  const handleSeek = useCallback((seconds: number) => {
    if (playerRef.current) {
      playerRef.current.seekTo(seconds, "seconds");
      setIsPlaying(true);
    }
  }, []);

  const togglePlay = useCallback(() => setIsPlaying((p) => !p), []);

  const handleProgress = useCallback(
    ({ playedSeconds }: { playedSeconds: number }) => setCurrentTime(playedSeconds),
    []
  );

  const handleDuration = useCallback((d: number) => setDuration(d), []);

  return {
    playerRef,
    isPlaying,
    setIsPlaying,
    currentTime,
    duration,
    handleSeek,
    togglePlay,
    handleProgress,
    handleDuration,
  };
}
