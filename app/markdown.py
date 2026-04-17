from __future__ import annotations

from typing import Iterable

from app.types import JobRecord, TranscriptSegment


def format_timestamp(seconds: float) -> str:
    safe_seconds = max(0, int(seconds))
    hours = safe_seconds // 3600
    minutes = (safe_seconds % 3600) // 60
    secs = safe_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _render_header(title: str, job: JobRecord) -> list[str]:
    created = job.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    return [
        f"# {title}",
        "",
        f"- Файл: `{job.original_filename}`",
        f"- Модель: `{job.model_id}`",
        "- Язык: `ru`",
        f"- Создано: `{created}`",
        "",
        "## Текст",
        "",
    ]


def render_transcript_markdown(job: JobRecord, segments: Iterable[TranscriptSegment]) -> str:
    lines = _render_header("Стенограмма", job)

    any_segment = False
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        any_segment = True
        if job.include_timestamps:
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            lines.append(f"[{start} - {end}] {text}")
        else:
            lines.append(text)
        lines.append("")

    if not any_segment:
        lines.append("_Речь не распознана._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_readable_markdown(job: JobRecord, paragraphs: Iterable[str]) -> str:
    lines = _render_header("Читабельный текст", job)

    any_paragraph = False
    for paragraph in paragraphs:
        text = paragraph.strip()
        if not text:
            continue
        any_paragraph = True
        lines.append(text)
        lines.append("")

    if not any_paragraph:
        lines.append("_Речь не распознана._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
