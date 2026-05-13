"use client";

import { useCallback } from "react";
import { documentsApi, pollDocumentReady } from "@/lib/api";
import { useAppStore } from "@/store/appStore";
import { getErrorMessage } from "@/lib/utils";

export function useUpload() {
  const { addUpload, updateUpload, removeUpload, upsertDocument } = useAppStore();

  const uploadFile = useCallback(
    async (file: File) => {
      addUpload({ file_name: file.name, progress: 0, status: "uploading" });

      try {
        // 1. Upload the file
        const { data: doc } = await documentsApi.upload(file, (pct) => {
          updateUpload(file.name, { progress: pct });
        });

        updateUpload(file.name, {
          progress: 100,
          status: "processing",
          document_id: doc.id,
        });
        upsertDocument(doc);

        // 2. Poll until ready or error
        await pollDocumentReady(
          doc.id,
          (updated) => {
            upsertDocument(updated);
            if (updated.status === "ready") {
              updateUpload(file.name, { status: "done" });
            } else if (updated.status === "error") {
              updateUpload(file.name, {
                status: "error",
                error: updated.error_message || "Processing failed",
              });
            }
          }
        );

        // Auto-remove from upload queue after 3s
        setTimeout(() => removeUpload(file.name), 3000);
      } catch (err) {
        updateUpload(file.name, {
          status: "error",
          error: getErrorMessage(err),
        });
        setTimeout(() => removeUpload(file.name), 5000);
      }
    },
    [addUpload, updateUpload, removeUpload, upsertDocument]
  );

  const uploadMultiple = useCallback(
    (files: File[]) => Promise.all(files.map(uploadFile)),
    [uploadFile]
  );

  return { uploadFile, uploadMultiple };
}
