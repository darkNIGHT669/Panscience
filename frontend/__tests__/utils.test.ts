import { formatBytes, formatDuration, formatTimestamp, getErrorMessage, cn, fileTypeIcon, fileTypeLabel } from "@/lib/utils";

describe("formatBytes", () => {
  it("formats 0 bytes", () => expect(formatBytes(0)).toBe("0 B"));
  it("formats kilobytes", () => expect(formatBytes(1024)).toBe("1 KB"));
  it("formats megabytes", () => expect(formatBytes(1024 * 1024)).toBe("1 MB"));
  it("formats gigabytes", () => expect(formatBytes(1024 * 1024 * 1024)).toBe("1 GB"));
  it("formats partial MB", () => expect(formatBytes(1536 * 1024)).toBe("1.5 MB"));
});

describe("formatDuration", () => {
  it("formats seconds only", () => expect(formatDuration(45)).toBe("0:45"));
  it("formats minutes and seconds", () => expect(formatDuration(125)).toBe("2:05"));
  it("formats hours", () => expect(formatDuration(3661)).toBe("1:01:01"));
  it("formats zero", () => expect(formatDuration(0)).toBe("0:00"));
  it("pads single-digit seconds", () => expect(formatDuration(65)).toBe("1:05"));
});

describe("formatTimestamp", () => {
  it("delegates to formatDuration", () => {
    expect(formatTimestamp(120)).toBe(formatDuration(120));
  });
});

describe("getErrorMessage", () => {
  it("extracts Error message", () => {
    expect(getErrorMessage(new Error("something broke"))).toBe("something broke");
  });

  it("extracts Axios detail", () => {
    const err = { response: { data: { detail: "Not found" } } };
    expect(getErrorMessage(err)).toBe("Not found");
  });

  it("falls back to generic message", () => {
    expect(getErrorMessage(null)).toBe("An unexpected error occurred");
    expect(getErrorMessage(42)).toBe("An unexpected error occurred");
  });
});

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("resolves Tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });
});

describe("fileTypeIcon", () => {
  it("returns correct emoji for pdf", () => expect(fileTypeIcon("pdf")).toBe("📄"));
  it("returns correct emoji for audio", () => expect(fileTypeIcon("audio")).toBe("🎵"));
  it("returns correct emoji for video", () => expect(fileTypeIcon("video")).toBe("🎬"));
  it("returns default for unknown", () => expect(fileTypeIcon("xyz")).toBe("📁"));
});

describe("fileTypeLabel", () => {
  it("returns label for pdf", () => expect(fileTypeLabel("pdf")).toBe("PDF Document"));
  it("returns label for audio", () => expect(fileTypeLabel("audio")).toBe("Audio File"));
  it("returns label for video", () => expect(fileTypeLabel("video")).toBe("Video File"));
  it("returns default for unknown", () => expect(fileTypeLabel("xyz")).toBe("File"));
});
