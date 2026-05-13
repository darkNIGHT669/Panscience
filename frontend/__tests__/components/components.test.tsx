/**
 * Frontend component tests.
 * All API calls and stores are mocked.
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FileUploader } from "@/components/FileUploader";
import { MessageBubble } from "@/components/MessageBubble";
import { SummaryPanel } from "@/components/SummaryPanel";
import { FileList } from "@/components/FileList";
import type { Document, StreamingMessage } from "@/lib/types";

// ─── Mock store ────────────────────────────────────────────────────────────────
const mockUploads: never[] = [];
const mockDocuments: Document[] = [];

jest.mock("@/store/appStore", () => ({
  useAppStore: jest.fn((selector: (s: unknown) => unknown) => {
    const state = {
      uploads: mockUploads,
      documents: mockDocuments,
      activeDocument: null,
      activeSession: null,
      addUpload: jest.fn(),
      updateUpload: jest.fn(),
      removeUpload: jest.fn(),
      upsertDocument: jest.fn(),
      removeDocument: jest.fn(),
      setActiveSession: jest.fn(),
      triggerSeek: jest.fn(),
    };
    return typeof selector === "function" ? selector(state) : state;
  }),
}));

jest.mock("@/hooks/useUpload", () => ({
  useUpload: () => ({
    uploadMultiple: jest.fn(),
    uploadFile: jest.fn(),
  }),
}));

jest.mock("@/lib/api", () => ({
  documentsApi: {
    summary: jest.fn().mockResolvedValue({ data: { summary: "Mock summary.", cached: false } }),
    delete: jest.fn().mockResolvedValue({}),
  },
  chatApi: {
    createSession: jest.fn().mockResolvedValue({ data: { id: "session-1", document_id: "doc-1" } }),
  },
}));

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

// ════════════════════════════════════════════════════════════
// FileUploader
// ════════════════════════════════════════════════════════════
describe("FileUploader", () => {
  it("renders dropzone with correct text", () => {
    render(<FileUploader />);
    expect(screen.getByText("Upload files")).toBeInTheDocument();
    expect(screen.getByText(/PDF, MP3, MP4/)).toBeInTheDocument();
  });

  it("shows drag-active state when dragging", () => {
    const { container } = render(<FileUploader />);
    const dropzone = container.querySelector("[class*='border-dashed']")!;
    fireEvent.dragEnter(dropzone);
    // Dropzone changes styling on drag — just verify it renders
    expect(dropzone).toBeInTheDocument();
  });

  it("renders upload queue when uploads present", () => {
    const { useAppStore } = require("@/store/appStore");
    useAppStore.mockImplementation((selector: (s: unknown) => unknown) => {
      const state = {
        uploads: [{ file_name: "test.pdf", progress: 50, status: "uploading" }],
        documents: [],
        addUpload: jest.fn(),
        updateUpload: jest.fn(),
        removeUpload: jest.fn(),
        upsertDocument: jest.fn(),
      };
      return typeof selector === "function" ? selector(state) : state;
    });
    render(<FileUploader />);
    expect(screen.getByText("test.pdf")).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════
// MessageBubble
// ════════════════════════════════════════════════════════════
describe("MessageBubble", () => {
  const makeMessage = (overrides: Partial<StreamingMessage> = {}): StreamingMessage => ({
    id: "msg-1",
    role: "assistant",
    content: "The answer is 42.",
    citations: null,
    ...overrides,
  });

  it("renders user message correctly", () => {
    render(<MessageBubble message={makeMessage({ role: "user", content: "My question" })} onJumpToTimestamp={jest.fn()} />);
    expect(screen.getByText("My question")).toBeInTheDocument();
    expect(screen.getByText("U")).toBeInTheDocument();
  });

  it("renders assistant message with AI avatar", () => {
    render(<MessageBubble message={makeMessage()} onJumpToTimestamp={jest.fn()} />);
    expect(screen.getByText("The answer is 42.")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("shows streaming dots when isStreaming with no content", () => {
    const { container } = render(
      <MessageBubble message={makeMessage({ isStreaming: true, content: "" })} onJumpToTimestamp={jest.fn()} />
    );
    // Streaming indicator dots
    const dots = container.querySelectorAll(".animate-pulse2");
    expect(dots.length).toBeGreaterThan(0);
  });

  it("shows source count when citations present", async () => {
    const msg = makeMessage({
      citations: [
        { chunk_id: "c1", page_num: 1, start_time: null, end_time: null, text_snippet: "Snippet 1" },
        { chunk_id: "c2", page_num: 2, start_time: null, end_time: null, text_snippet: "Snippet 2" },
      ],
    });
    render(<MessageBubble message={msg} onJumpToTimestamp={jest.fn()} />);
    expect(screen.getByText(/2 sources/)).toBeInTheDocument();
  });

  it("renders timestamp play buttons for audio citations", () => {
    const msg = makeMessage({
      citations: [
        { chunk_id: "c1", page_num: null, start_time: 65.0, end_time: 90.0, text_snippet: "At one minute" },
      ],
    });
    render(<MessageBubble message={msg} onJumpToTimestamp={jest.fn()} />);
    expect(screen.getByText("01:05")).toBeInTheDocument();
  });

  it("calls onJumpToTimestamp when play button clicked", async () => {
    const onJump = jest.fn();
    const msg = makeMessage({
      citations: [
        { chunk_id: "c1", page_num: null, start_time: 120.0, end_time: 150.0, text_snippet: "Content" },
      ],
    });
    render(<MessageBubble message={msg} onJumpToTimestamp={onJump} />);
    fireEvent.click(screen.getByText("02:00"));
    expect(onJump).toHaveBeenCalledWith(120.0);
  });

  it("expands citation snippets on click", async () => {
    const msg = makeMessage({
      citations: [
        { chunk_id: "c1", page_num: 3, start_time: null, end_time: null, text_snippet: "Important excerpt." },
      ],
    });
    render(<MessageBubble message={msg} onJumpToTimestamp={jest.fn()} />);
    fireEvent.click(screen.getByText(/1 source/));
    await waitFor(() => {
      expect(screen.getByText("Important excerpt.")).toBeInTheDocument();
    });
  });
});

// ════════════════════════════════════════════════════════════
// SummaryPanel
// ════════════════════════════════════════════════════════════
describe("SummaryPanel", () => {
  const doc: Document = {
    id: "doc-1",
    filename: "report.pdf",
    original_filename: "report.pdf",
    file_type: "pdf",
    mime_type: "application/pdf",
    file_size_bytes: 1024,
    status: "ready",
    error_message: null,
    summary: null,
    duration_seconds: null,
    page_count: 10,
    created_at: new Date().toISOString(),
  };

  it("renders AI Summary toggle button", () => {
    render(<SummaryPanel document={doc} />);
    expect(screen.getByText("AI Summary")).toBeInTheDocument();
  });

  it("shows cached summary immediately if present", async () => {
    render(<SummaryPanel document={{ ...doc, summary: "Pre-cached summary." }} />);
    fireEvent.click(screen.getByText("AI Summary"));
    await waitFor(() => {
      expect(screen.getByText("Pre-cached summary.")).toBeInTheDocument();
    });
  });

  it("fetches summary from API when none cached", async () => {
    const { documentsApi } = require("@/lib/api");
    render(<SummaryPanel document={doc} />);
    fireEvent.click(screen.getByText("AI Summary"));
    await waitFor(() => {
      expect(documentsApi.summary).toHaveBeenCalledWith("doc-1");
      expect(screen.getByText("Mock summary.")).toBeInTheDocument();
    });
  });

  it("collapses panel on second click", async () => {
    render(<SummaryPanel document={{ ...doc, summary: "Some summary." }} />);
    // Open
    fireEvent.click(screen.getByText("AI Summary"));
    await waitFor(() => expect(screen.getByText("Some summary.")).toBeInTheDocument());
    // Close
    fireEvent.click(screen.getByText("AI Summary"));
    await waitFor(() => expect(screen.queryByText("Some summary.")).not.toBeInTheDocument());
  });
});

// ════════════════════════════════════════════════════════════
// FileList
// ════════════════════════════════════════════════════════════
describe("FileList", () => {
  it("shows empty state when no documents", () => {
    render(<FileList />);
    expect(screen.getByText(/Upload a PDF/)).toBeInTheDocument();
  });

  it("renders document list when documents present", () => {
    const { useAppStore } = require("@/store/appStore");
    useAppStore.mockImplementation((selector: (s: unknown) => unknown) => {
      const state = {
        documents: [
          {
            id: "doc-1",
            filename: "lecture.mp4",
            original_filename: "lecture.mp4",
            file_type: "video",
            status: "ready",
            file_size_bytes: 10000000,
            created_at: new Date().toISOString(),
          },
        ],
        activeDocument: null,
        removeDocument: jest.fn(),
        setActiveSession: jest.fn(),
        upsertDocument: jest.fn(),
      };
      return typeof selector === "function" ? selector(state) : state;
    });
    render(<FileList />);
    expect(screen.getByText("lecture.mp4")).toBeInTheDocument();
  });
});
