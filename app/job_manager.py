from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from shutil import copy2
import threading
import uuid

from app.config import Settings
from app.markdown import render_readable_markdown
from app.model_manager import FasterWhisperModelManager
from app.readable_text import ReadableTextProcessor
from app.runtime_logging import write_runtime_trace
from app.services.asr_factory import ASRFactory
from app.services.asr_base import JobCancelledError
from app.services.ffmpeg_service import FfmpegService
from app.types import EngineType, JobRecord, JobStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobManagerError(Exception):
    """Base exception for job manager errors."""


class JobNotFoundError(JobManagerError):
    """Raised when job is missing."""


class JobStateError(JobManagerError):
    """Raised when job operation is not allowed in current state."""


class JobManager:
    def __init__(
        self,
        settings: Settings,
        ffmpeg_service: FfmpegService | None = None,
        asr_factory: ASRFactory | None = None,
        readable_processor: ReadableTextProcessor | None = None,
        model_manager: FasterWhisperModelManager | None = None,
    ) -> None:
        self.settings = settings
        self.model_manager = model_manager or FasterWhisperModelManager(settings)
        self.ffmpeg_service = ffmpeg_service or FfmpegService(settings.ffmpeg_path)
        self.asr_factory = asr_factory or ASRFactory(settings, self.model_manager)
        self.readable_processor = readable_processor or ReadableTextProcessor(
            settings.rupunct_model_path,
            punct_device=settings.readable_punct_device,
        )

        self._lock = threading.RLock()
        self._jobs: dict[str, JobRecord] = {}
        self._pending: deque[str] = deque()
        self._cancel_events: dict[str, threading.Event] = {}

        self._new_job_event = asyncio.Event()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._load_persisted_history()

    @property
    def _history_path(self) -> Path:
        return self.settings.storage_dir / "job_history.json"

    @staticmethod
    def _normalize_variant(variant: str) -> str:
        if variant != "readable":
            raise JobStateError("Unsupported document variant.")
        return "readable"

    def _variant_paths(
        self,
        job: JobRecord,
        variant: str,
    ) -> tuple[Path | None, Path | None, datetime | None]:
        self._normalize_variant(variant)
        return (
            job.readable_result_path,
            job.readable_override_path,
            job.readable_editor_updated_at,
        )

    def _variant_override_path(self, job_id: str, variant: str) -> Path:
        self._normalize_variant(variant)
        return self.settings.results_dir / f"{job_id}.readable.user.md"

    def _set_variant_override(
        self,
        job: JobRecord,
        variant: str,
        path: Path | None,
        updated_at: datetime | None,
    ) -> None:
        self._normalize_variant(variant)
        job.readable_override_path = path
        job.readable_editor_updated_at = updated_at

    def _serialize_document_payload(
        self,
        job: JobRecord,
        variant: str,
        *,
        markdown: str,
        base_available: bool,
    ) -> dict:
        normalized_variant = self._normalize_variant(variant)
        _, override_path, updated_at = self._variant_paths(job, normalized_variant)
        edited = self._path_exists(override_path)
        return {
            "variant": normalized_variant,
            "markdown": markdown,
            "edited": edited,
            "updated_at": updated_at.isoformat() if edited and updated_at else None,
            "base_available": base_available,
        }

    def _serialize_job_history_record(self, job: JobRecord) -> dict[str, object]:
        return {
            "job_id": job.job_id,
            "original_filename": job.original_filename,
            "input_path": str(job.input_path),
            "engine": job.engine.value,
            "model_id": job.model_id,
            "include_timestamps": job.include_timestamps,
            "retry_of_job_id": job.retry_of_job_id,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "readable_result_path": str(job.readable_result_path) if job.readable_result_path else None,
            "readable_override_path": str(job.readable_override_path) if job.readable_override_path else None,
            "readable_editor_updated_at": (
                job.readable_editor_updated_at.isoformat() if job.readable_editor_updated_at else None
            ),
            "segments_count": job.segments_count,
        }

    def _persist_history(self) -> None:
        with self._lock:
            items = [
                self._serialize_job_history_record(job)
                for job in sorted(self._jobs.values(), key=lambda item: item.created_at)
                if job.status in (JobStatus.done, JobStatus.failed, JobStatus.cancelled)
            ]

        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        self._history_path.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_persisted_history(self) -> None:
        try:
            if not self._history_path.exists():
                return
            payload = json.loads(self._history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        items = payload.get("items")
        if not isinstance(items, list):
            return

        loaded: dict[str, JobRecord] = {}
        for raw in items:
            if not isinstance(raw, dict):
                continue
            try:
                status = JobStatus(str(raw["status"]))
                if status not in (JobStatus.done, JobStatus.failed, JobStatus.cancelled):
                    continue
                record = JobRecord(
                    job_id=str(raw["job_id"]),
                    original_filename=str(raw["original_filename"]),
                    input_path=Path(str(raw["input_path"])),
                    engine=EngineType(str(raw["engine"])),
                    model_id=str(raw["model_id"]),
                    include_timestamps=bool(raw["include_timestamps"]),
                    retry_of_job_id=raw.get("retry_of_job_id"),
                    status=status,
                    progress_percent=int(raw.get("progress_percent", 0) or 0),
                    error=raw.get("error"),
                    created_at=datetime.fromisoformat(str(raw["created_at"])),
                    started_at=(
                        datetime.fromisoformat(str(raw["started_at"]))
                        if raw.get("started_at")
                        else None
                    ),
                    finished_at=(
                        datetime.fromisoformat(str(raw["finished_at"]))
                        if raw.get("finished_at")
                        else None
                    ),
                    readable_result_path=(
                        Path(str(raw["readable_result_path"]))
                        if raw.get("readable_result_path")
                        else None
                    ),
                    readable_override_path=(
                        Path(str(raw["readable_override_path"]))
                        if raw.get("readable_override_path")
                        else None
                    ),
                    readable_editor_updated_at=(
                        datetime.fromisoformat(str(raw["readable_editor_updated_at"]))
                        if raw.get("readable_editor_updated_at")
                        else None
                    ),
                    segments_count=int(raw.get("segments_count", 0) or 0),
                )
            except Exception:
                continue
            loaded[record.job_id] = record

        self._jobs.update(loaded)

    def get_document_payload(self, job_id: str, variant: str) -> dict:
        normalized_variant = self._normalize_variant(variant)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            snapshot = replace(job)

        payload = self._serialize_job_snapshot(snapshot, now=utcnow(), queue_position=0)
        if payload["status"] != JobStatus.done.value:
            raise JobStateError("Result is not ready.")
        base_path, override_path, _ = self._variant_paths(snapshot, normalized_variant)
        base_available = self._path_exists(base_path)
        effective_path = override_path if self._path_exists(override_path) else base_path
        if effective_path is None or not self._path_exists(effective_path):
            raise FileNotFoundError(f"Document '{normalized_variant}' is unavailable.")

        return self._serialize_document_payload(
            snapshot,
            normalized_variant,
            markdown=effective_path.read_text(encoding="utf-8"),
            base_available=base_available,
        )

    def save_document_override(self, job_id: str, variant: str, markdown: str) -> dict:
        normalized_variant = self._normalize_variant(variant)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            snapshot = replace(job)

        payload = self._serialize_job_snapshot(snapshot, now=utcnow(), queue_position=0)
        if payload["status"] != JobStatus.done.value:
            raise JobStateError("Document editing is available only for completed jobs.")
        base_path, _, _ = self._variant_paths(snapshot, normalized_variant)
        if base_path is None or not self._path_exists(base_path):
            raise FileNotFoundError(f"Document '{normalized_variant}' is unavailable.")

        normalized_markdown = markdown.replace("\r\n", "\n")
        if normalized_markdown and not normalized_markdown.endswith("\n"):
            normalized_markdown += "\n"

        override_path = self._variant_override_path(job_id, normalized_variant)
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(normalized_markdown, encoding="utf-8")
        updated_at = utcnow()

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            self._set_variant_override(job, normalized_variant, override_path, updated_at)
            snapshot = replace(job)

        write_runtime_trace(f"job {job_id}: document override saved ({normalized_variant})")
        self._persist_history()
        return self._serialize_document_payload(
            snapshot,
            normalized_variant,
            markdown=normalized_markdown,
            base_available=True,
        )

    def reset_document_override(self, job_id: str, variant: str) -> dict:
        normalized_variant = self._normalize_variant(variant)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            snapshot = replace(job)

        payload = self._serialize_job_snapshot(snapshot, now=utcnow(), queue_position=0)
        if payload["status"] != JobStatus.done.value:
            raise JobStateError("Document editing is available only for completed jobs.")
        base_path, override_path, _ = self._variant_paths(snapshot, normalized_variant)
        if base_path is None or not self._path_exists(base_path):
            raise FileNotFoundError(f"Document '{normalized_variant}' is unavailable.")

        if override_path is not None:
            try:
                override_path.unlink(missing_ok=True)
            except OSError:
                pass

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            self._set_variant_override(job, normalized_variant, None, None)
            snapshot = replace(job)

        write_runtime_trace(f"job {job_id}: document override reset ({normalized_variant})")
        self._persist_history()
        return self._serialize_document_payload(
            snapshot,
            normalized_variant,
            markdown=base_path.read_text(encoding="utf-8"),
            base_available=True,
        )

    def get_effective_document_path(self, job_id: str, variant: str) -> tuple[dict, Path]:
        normalized_variant = self._normalize_variant(variant)
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            snapshot = replace(job)

        payload = self._serialize_job_snapshot(snapshot, now=utcnow(), queue_position=0)
        if payload["status"] != JobStatus.done.value:
            raise JobStateError("Result is not ready.")
        base_path, override_path, _ = self._variant_paths(snapshot, normalized_variant)
        effective_path = override_path if self._path_exists(override_path) else base_path
        if effective_path is None or not self._path_exists(effective_path):
            raise FileNotFoundError(f"Document '{normalized_variant}' is unavailable.")
        return payload, effective_path

    async def start(self) -> None:
        if self._running:
            return
        self.settings.ensure_directories()
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop(), name="voctarium-worker")

    async def shutdown(self) -> None:
        if not self._running:
            return
        self._running = False
        self._new_job_event.set()

        tasks = [task for task in (self._worker_task,) if task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._worker_task = None

    def create_job(
        self,
        *,
        input_path: Path,
        original_filename: str,
        model_id: str | None = None,
        include_timestamps: bool,
        retry_of_job_id: str | None = None,
    ) -> tuple[JobRecord, int]:
        resolved_model_id = self.model_manager.ensure_model_available(
            model_id or self.model_manager.active_model_id()
        )
        job_id = uuid.uuid4().hex
        record = JobRecord(
            job_id=job_id,
            original_filename=original_filename,
            input_path=input_path,
            engine=EngineType.faster_whisper,
            model_id=resolved_model_id,
            include_timestamps=include_timestamps,
            retry_of_job_id=retry_of_job_id,
            status=JobStatus.queued,
            progress_percent=0,
        )

        with self._lock:
            self._jobs[job_id] = record
            self._pending.append(job_id)
            queue_position = len(self._pending)

        self._new_job_event.set()
        return replace(record), queue_position

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return replace(job)

    def get_job_payload(self, job_id: str) -> dict | None:
        now = utcnow()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            snapshot = replace(job)
            queue_position = self._queue_position_unlocked(job_id)

        return self._serialize_job_snapshot(snapshot, now=now, queue_position=queue_position)

    def list_job_payloads(self, limit: int = 50) -> tuple[list[dict], int]:
        safe_limit = max(1, int(limit))
        now = utcnow()
        with self._lock:
            queue_positions = {job_id: index + 1 for index, job_id in enumerate(self._pending)}
            all_jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            total = len(all_jobs)
            selected = [replace(item) for item in all_jobs[:safe_limit]]

        payloads = [
            self._serialize_job_snapshot(
                item,
                now=now,
                queue_position=queue_positions.get(item.job_id, 0),
            )
            for item in selected
        ]
        return payloads, total

    def retry_job(
        self,
        *,
        job_id: str,
        include_timestamps_override: bool | None = None,
    ) -> tuple[JobRecord, int]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            snapshot = replace(job)

        if snapshot.status not in (JobStatus.done, JobStatus.failed, JobStatus.cancelled):
            raise JobStateError("Retry is available only for done/failed/cancelled jobs.")

        payload = self._serialize_job_snapshot(snapshot, now=utcnow(), queue_position=0)
        if not payload["source_available"]:
            raise JobStateError("Source file is unavailable for retry.")
        try:
            resolved_model_id = self.model_manager.ensure_model_available(snapshot.model_id)
        except Exception as exc:
            raise JobStateError("Original faster-whisper model is unavailable for retry.") from exc

        target_timestamps = (
            include_timestamps_override
            if include_timestamps_override is not None
            else snapshot.include_timestamps
        )

        source_path = snapshot.input_path
        suffix = source_path.suffix or Path(snapshot.original_filename).suffix or ".bin"
        retry_path = self.settings.uploads_dir / f"{uuid.uuid4().hex}_retry{suffix}"

        try:
            retry_path.parent.mkdir(parents=True, exist_ok=True)
            copy2(source_path, retry_path)
        except FileNotFoundError as exc:
            raise JobStateError("Source file is unavailable for retry.") from exc
        except OSError as exc:
            raise JobStateError(f"Cannot prepare retry input: {exc}") from exc

        return self.create_job(
            input_path=retry_path,
            original_filename=snapshot.original_filename,
            model_id=resolved_model_id,
            include_timestamps=target_timestamps,
            retry_of_job_id=snapshot.job_id,
        )

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status == JobStatus.processing:
                raise JobStateError("Cannot delete a processing job.")

            if job.status == JobStatus.queued:
                self._pending = deque(item for item in self._pending if item != job_id)
                if not self._pending:
                    self._new_job_event.clear()

            removed = self._jobs.pop(job_id, None)

        if removed is None:
            return False
        self._delete_job_files(removed)
        self._persist_history()
        return True

    def cancel_job(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(f"Job '{job_id}' not found.")
            if job.status != JobStatus.processing:
                raise JobStateError("Only a processing job can be cancelled.")

            cancel_event = self._cancel_events.get(job_id)
            if cancel_event is None:
                raise JobStateError("Cancellation is not available for this job.")
            cancel_event.set()
            return replace(job)

    def health_payload(self) -> dict:
        with self._lock:
            queue_size = len(self._pending)
            jobs_total = len(self._jobs)

        worker_running = self._worker_task is not None and not self._worker_task.done()
        ffmpeg_available = self.ffmpeg_service.is_available()
        engines = self.asr_factory.readiness()
        status = "ok" if worker_running and ffmpeg_available else "degraded"

        return {
            "status": status,
            "worker_running": worker_running,
            "queue_size": queue_size,
            "jobs_total": jobs_total,
            "ffmpeg_available": ffmpeg_available,
            "engines": engines,
            "active_faster_whisper_model": self.model_manager.active_model_id(),
            "timestamp": utcnow().isoformat(),
        }

    def is_model_locked(self, model_id: str) -> bool:
        with self._lock:
            for job in self._jobs.values():
                if job.model_id != model_id:
                    continue
                if job.status in (JobStatus.queued, JobStatus.processing):
                    return True
        return False

    def run_cleanup_once(self) -> int:
        return 0

    async def _worker_loop(self) -> None:
        while self._running:
            await self._new_job_event.wait()
            if not self._running:
                return

            next_job_id: str | None = None
            with self._lock:
                if self._pending:
                    next_job_id = self._pending.popleft()
                if not self._pending:
                    self._new_job_event.clear()

            if next_job_id is None:
                continue
            await self._process_job(next_job_id)

    async def _process_job(self, job_id: str) -> None:
        cancel_event = threading.Event()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = JobStatus.processing
            job.started_at = utcnow()
            job.progress_percent = 1
            job.error = None
            input_path = job.input_path
            include_timestamps = job.include_timestamps
            original_filename = job.original_filename
            engine_type = job.engine
            model_id = job.model_id
            created_at = job.created_at
            self._cancel_events[job_id] = cancel_event

        write_runtime_trace(f"job {job_id}: processing started ({engine_type.value}:{model_id})")
        normalized_path = self.settings.work_dir / f"{job_id}.wav"
        readable_result_path = self.settings.results_dir / f"{job_id}.readable.md"
        audio_duration_seconds = 0.0

        try:
            write_runtime_trace(f"job {job_id}: ffmpeg convert begin")
            audio_duration_seconds = await asyncio.to_thread(
                self.ffmpeg_service.convert_to_wav,
                input_path,
                normalized_path,
                cancel_event,
            )
            write_runtime_trace(
                f"job {job_id}: ffmpeg convert done duration={audio_duration_seconds:.2f}s"
            )
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.normalized_path = normalized_path
                job.progress_percent = max(job.progress_percent, 10)
            self._raise_if_cancelled(cancel_event)

            write_runtime_trace(f"job {job_id}: resolving engine {engine_type.value}:{model_id}")
            engine = self.asr_factory.get(model_id)
            write_runtime_trace(f"job {job_id}: engine ready {engine_type.value}:{model_id}")

            def progress_callback(current_seconds: float) -> None:
                if audio_duration_seconds <= 0:
                    return
                ratio = min(max(current_seconds / audio_duration_seconds, 0.0), 1.0)
                mapped = 10 + int(ratio * 85)
                self._set_progress(job_id, mapped)

            write_runtime_trace(f"job {job_id}: transcription begin")
            segments = await asyncio.to_thread(
                engine.transcribe,
                normalized_path,
                "ru",
                progress_callback,
                cancel_event,
            )
            write_runtime_trace(f"job {job_id}: transcription done segments={len(segments)}")
            self._raise_if_cancelled(cancel_event)

            render_job = JobRecord(
                job_id=job_id,
                original_filename=original_filename,
                input_path=input_path,
                engine=engine_type,
                model_id=model_id,
                include_timestamps=include_timestamps,
                created_at=created_at,
            )
            write_runtime_trace(f"job {job_id}: readable render begin")
            readable_paragraphs = self.readable_processor.build_paragraphs(engine_type, segments)
            self._raise_if_cancelled(cancel_event)
            readable_markdown = render_readable_markdown(render_job, readable_paragraphs)
            readable_result_path.write_text(readable_markdown, encoding="utf-8")
            write_runtime_trace(f"job {job_id}: readable markdown saved")

            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                if self._path_exists(readable_result_path):
                    job.readable_result_path = readable_result_path
                job.progress_percent = 100
                job.status = JobStatus.done
                job.finished_at = utcnow()
                job.segments_count = len(segments)
            write_runtime_trace(f"job {job_id}: completed")
            self._persist_history()
        except JobCancelledError as exc:
            write_runtime_trace(f"job {job_id}: cancelled")
            for path in (readable_result_path,):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.status = JobStatus.cancelled
                job.error = str(exc)
                job.finished_at = utcnow()
                job.readable_result_path = None
            self._persist_history()
        except Exception as exc:
            write_runtime_trace(f"job {job_id}: failed {exc}")
            try:
                readable_result_path.unlink(missing_ok=True)
            except OSError:
                pass
            with self._lock:
                job = self._jobs.get(job_id)
                if job is None:
                    return
                job.status = JobStatus.failed
                job.error = str(exc)
                job.finished_at = utcnow()
                job.readable_result_path = None
            self._persist_history()
        finally:
            try:
                normalized_path.unlink(missing_ok=True)
            except OSError:
                pass
            with self._lock:
                self._cancel_events.pop(job_id, None)
                job = self._jobs.get(job_id)
                if job is not None:
                    job.normalized_path = None

    def _set_progress(self, job_id: str, progress: int) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.status != JobStatus.processing:
                return
            if progress <= job.progress_percent:
                return
            job.progress_percent = min(progress, 99)

    def _queue_position_unlocked(self, job_id: str) -> int:
        try:
            return list(self._pending).index(job_id) + 1
        except ValueError:
            return 0

    @staticmethod
    def _raise_if_cancelled(cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            raise JobCancelledError("Job cancelled by user.")

    @staticmethod
    def _path_exists(path: Path | None) -> bool:
        if path is None:
            return False
        try:
            return path.exists()
        except OSError:
            return False

    def _serialize_job_snapshot(self, job: JobRecord, *, now: datetime, queue_position: int) -> dict:
        source_exists = self._path_exists(job.input_path)
        readable_exists = self._path_exists(job.readable_result_path)
        readable_override_exists = self._path_exists(job.readable_override_path)

        source_available = source_exists
        readable_available = readable_exists or readable_override_exists

        return {
            "job_id": job.job_id,
            "original_filename": job.original_filename,
            "status": job.status.value,
            "progress_percent": job.progress_percent,
            "queue_position": queue_position if job.status == JobStatus.queued else 0,
            "error": job.error,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "engine": job.engine.value,
            "model_id": job.model_id,
            "include_timestamps": job.include_timestamps,
            "segments_count": job.segments_count,
            "source_available": source_available,
            "readable_available": readable_available,
            "readable_edited": readable_override_exists,
            "readable_editor_updated_at": (
                job.readable_editor_updated_at.isoformat()
                if readable_override_exists and job.readable_editor_updated_at
                else None
            ),
            "retry_of_job_id": job.retry_of_job_id,
        }

    def _delete_job_files(self, job: JobRecord) -> bool:
        removed = False
        seen: set[str] = set()
        for path in (
            job.input_path,
            job.normalized_path,
            job.readable_result_path,
            job.readable_override_path,
        ):
            if path is None:
                continue
            path_key = str(path).lower()
            if path_key in seen:
                continue
            seen.add(path_key)
            try:
                if path.exists():
                    path.unlink()
                    removed = True
            except OSError:
                continue
        return removed
