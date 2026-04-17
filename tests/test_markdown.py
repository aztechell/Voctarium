from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.markdown import format_timestamp, render_readable_markdown, render_transcript_markdown
from app.types import EngineType, JobRecord, TranscriptSegment


def test_format_timestamp() -> None:
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(5) == "00:00:05"
    assert format_timestamp(3661) == "01:01:01"


def test_render_markdown_with_timestamps() -> None:
    job = JobRecord(
        job_id="job-1",
        original_filename="input.wav",
        input_path=Path("input.wav"),
        engine=EngineType.faster_whisper,
        model_id="medium",
        include_timestamps=True,
        created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
    )
    segments = [
        TranscriptSegment(start=1.2, end=4.9, text="Привет"),
        TranscriptSegment(start=6.0, end=8.0, text="Мир"),
    ]

    md = render_transcript_markdown(job, segments)

    assert "# Стенограмма" in md
    assert "- Модель: `medium`" in md
    assert "- Движок:" not in md
    assert "[00:00:01 - 00:00:04] Привет" in md
    assert "[00:00:06 - 00:00:08] Мир" in md


def test_render_markdown_without_timestamps() -> None:
    job = JobRecord(
        job_id="job-2",
        original_filename="input.wav",
        input_path=Path("input.wav"),
        engine=EngineType.faster_whisper,
        model_id="medium",
        include_timestamps=False,
    )
    segments = [TranscriptSegment(start=0.0, end=1.0, text="Текст")]

    md = render_transcript_markdown(job, segments)

    assert "Текст" in md
    assert "[00:00:00 - 00:00:01]" not in md


def test_render_readable_markdown() -> None:
    job = JobRecord(
        job_id="job-3",
        original_filename="lecture.wav",
        input_path=Path("lecture.wav"),
        engine=EngineType.faster_whisper,
        model_id="medium",
        include_timestamps=True,
        created_at=datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
    )

    md = render_readable_markdown(job, ["Первый абзац.", "Второй абзац."])

    assert "# Читабельный текст" in md
    assert "- Движок:" not in md
    assert "Первый абзац." in md
    assert "Второй абзац." in md
    assert "[00:00:" not in md
