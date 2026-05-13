"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useUpload } from "@/hooks/useUpload";
import { useAppStore } from "@/store/appStore";
import { cn, formatBytes } from "@/lib/utils";

const ACCEPT = {
  "application/pdf": [".pdf"],
  "audio/mpeg": [".mp3"],
  "audio/wav": [".wav"],
  "audio/mp4": [".m4a"],
  "audio/ogg": [".ogg"],
  "video/mp4": [".mp4"],
  "video/webm": [".webm"],
  "video/quicktime": [".mov"],
};

export function FileUploader() {
  const { uploadMultiple } = useUpload();
  const uploads = useAppStore((s) => s.uploads);
  const removeUpload = useAppStore((s) => s.removeUpload);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length) uploadMultiple(acceptedFiles);
    },
    [uploadMultiple]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPT,
    maxSize: 500 * 1024 * 1024, // 500 MB
    multiple: true,
  });

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-4 cursor-pointer transition-all duration-200 text-center",
          isDragActive
            ? "border-accent bg-accent/5 scale-[1.01]"
            : "border-surface-warm hover:border-accent/40 hover:bg-accent/3"
        )}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-2">
          <div className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center transition-colors",
            isDragActive ? "bg-accent text-white" : "bg-surface text-ink/40"
          )}>
            <Upload size={16} />
          </div>
          <div>
            <p className="text-xs font-medium text-ink/70">
              {isDragActive ? "Drop to upload" : "Upload files"}
            </p>
            <p className="text-[11px] text-ink/30 mt-0.5">PDF, MP3, MP4, WAV, MOV</p>
          </div>
        </div>
      </div>

      {/* Upload queue */}
      {uploads.length > 0 && (
        <div className="space-y-2">
          {uploads.map((up) => (
            <div key={up.file_name} className="bg-white rounded-lg p-2.5 border border-surface-warm animate-fade-up">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-ink truncate">{up.file_name}</p>
                </div>
                {up.status === "uploading" && (
                  <Loader2 size={12} className="text-accent animate-spin flex-shrink-0" />
                )}
                {up.status === "processing" && (
                  <Loader2 size={12} className="text-amber-qs animate-spin flex-shrink-0" />
                )}
                {up.status === "done" && (
                  <CheckCircle2 size={12} className="text-sage flex-shrink-0" />
                )}
                {up.status === "error" && (
                  <button onClick={() => removeUpload(up.file_name)}>
                    <X size={12} className="text-red-400 hover:text-red-600" />
                  </button>
                )}
              </div>

              {up.status !== "error" && (
                <div className="h-1 bg-surface-warm rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-300",
                      up.status === "done" ? "bg-sage" :
                      up.status === "processing" ? "bg-amber-qs" : "bg-accent"
                    )}
                    style={{ width: `${up.status === "processing" ? 100 : up.progress}%` }}
                  />
                </div>
              )}

              {up.status === "processing" && (
                <p className="text-[10px] text-ink/40 mt-1 font-mono">AI processing…</p>
              )}
              {up.status === "error" && (
                <div className="flex items-center gap-1 mt-1">
                  <AlertCircle size={10} className="text-red-400" />
                  <p className="text-[10px] text-red-400 truncate">{up.error}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
