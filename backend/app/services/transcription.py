"""
transcription.py
────────────────
Wraps the OpenAI Whisper API.
Uses response_format="verbose_json" to capture word/segment-level timestamps.
Handles files >25 MB by splitting into segments via ffmpeg before uploading.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import aiofiles
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24 MB safety margin (API limit is 25 MB)
FFMPEG_SEGMENT_SECONDS = 600           # 10-minute segments for large files


class TranscriptionService:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        self._client = client or AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(self, file_path: Path) -> dict[str, Any]:
        """
        Transcribe an audio or video file.
        Returns a dict with keys: text, segments, duration.
        Each segment has: id, start, end, text.
        """
        file_size = file_path.stat().st_size

        if file_size > WHISPER_MAX_BYTES:
            logger.info("File %s is %d bytes; splitting before transcription", file_path, file_size)
            return await self._transcribe_large_file(file_path)

        return await self._transcribe_single(file_path)

    # ─── Single-file transcription ────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _transcribe_single(self, file_path: Path) -> dict[str, Any]:
        logger.info("Transcribing %s via Whisper API", file_path.name)
        async with aiofiles.open(file_path, "rb") as f:
            audio_bytes = await f.read()

        # We pass a tuple (filename, bytes, mime) because the OpenAI SDK expects a file-like
        response = await self._client.audio.transcriptions.create(
            model=settings.WHISPER_MODEL,
            file=(file_path.name, audio_bytes, "audio/mpeg"),
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

        return self._normalize_response(response)

    # ─── Large file handling ──────────────────────────────────────────────────

    async def _transcribe_large_file(self, file_path: Path) -> dict[str, Any]:
        """Split file into segments using ffmpeg, transcribe each, merge results."""
        segments_dir = Path(tempfile.mkdtemp())
        try:
            segment_paths = await self._split_with_ffmpeg(file_path, segments_dir)
            all_segments: list[dict] = []
            full_text_parts: list[str] = []
            total_duration = 0.0

            for seg_path in sorted(segment_paths):
                result = await self._transcribe_single(seg_path)
                offset = total_duration

                for seg in result.get("segments", []):
                    all_segments.append({
                        **seg,
                        "start": seg["start"] + offset,
                        "end": seg["end"] + offset,
                    })

                full_text_parts.append(result.get("text", ""))
                total_duration += result.get("duration", 0.0)

            return {
                "text": " ".join(full_text_parts),
                "segments": all_segments,
                "duration": total_duration,
            }
        finally:
            # Cleanup temp segment files
            for f in segments_dir.iterdir():
                f.unlink(missing_ok=True)
            segments_dir.rmdir()

    async def _split_with_ffmpeg(self, input_path: Path, output_dir: Path) -> list[Path]:
        """Use ffmpeg to split a large file into N-minute MP3 segments."""
        pattern = str(output_dir / "segment_%03d.mp3")
        cmd = [
            "ffmpeg", "-i", str(input_path),
            "-f", "segment",
            "-segment_time", str(FFMPEG_SEGMENT_SECONDS),
            "-ac", "1",          # mono
            "-ar", "16000",      # 16 kHz (Whisper-optimised)
            "-b:a", "64k",       # low bitrate to keep under 25 MB
            "-vn",               # strip video stream
            "-y",                # overwrite
            pattern,
        ]
        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, text=True),
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr}")

        return sorted(output_dir.glob("segment_*.mp3"))

    # ─── Response normalisation ───────────────────────────────────────────────

    @staticmethod
    def _normalize_response(response: Any) -> dict[str, Any]:
        """
        Convert the OpenAI Transcription object to a plain dict.
        Handles both verbose_json (has .segments) and plain text responses.
        """
        if hasattr(response, "model_dump"):
            data = response.model_dump()
        elif hasattr(response, "__dict__"):
            data = vars(response)
        else:
            data = {"text": str(response), "segments": [], "duration": 0.0}

        segments = []
        for seg in data.get("segments") or []:
            segments.append({
                "id": seg.get("id", 0),
                "start": float(seg.get("start", 0.0)),
                "end": float(seg.get("end", 0.0)),
                "text": seg.get("text", "").strip(),
            })

        return {
            "text": data.get("text", ""),
            "segments": segments,
            "duration": float(data.get("duration", 0.0)),
            "language": data.get("language", "en"),
        }
