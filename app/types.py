from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class EngineType(str, Enum):
    faster_whisper = "faster_whisper"


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class JobRecord:
    job_id: str
    original_filename: str
    input_path: Path
    engine: EngineType
    model_id: str
    include_timestamps: bool
    retry_of_job_id: str | None = None
    status: JobStatus = JobStatus.queued
    progress_percent: int = 0
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    normalized_path: Path | None = None
    readable_result_path: Path | None = None
    readable_override_path: Path | None = None
    readable_editor_updated_at: datetime | None = None
    segments_count: int = 0
