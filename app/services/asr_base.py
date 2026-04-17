from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Callable, Protocol

from app.types import TranscriptSegment


ProgressCallback = Callable[[float], None]
CancelEvent = Event


class JobCancelledError(Exception):
    """Raised when processing is cancelled by user request."""


class ASREngine(Protocol):
    def transcribe(
        self,
        wav_path: Path,
        language: str,
        progress_callback: ProgressCallback | None = None,
        cancel_event: CancelEvent | None = None,
    ) -> list[TranscriptSegment]:
        """Return transcript segments from normalized WAV input."""
