from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time

from app.job_manager import JobManager, JobStateError
from tests.conftest import FakeASRFactory, FakeFfmpegService, make_test_wav


class CountingWaveformFfmpegService(FakeFfmpegService):
    def __init__(self) -> None:
        super().__init__()
        self.waveform_calls = 0

    def extract_waveform(self, input_path, *, points: int = 900) -> dict:
        del input_path
        self.waveform_calls += 1
        return {
            "points": points,
            "peaks": [0.5 for _ in range(points)],
            "duration_seconds": 12.5,
        }


async def wait_for_status(
    manager: JobManager,
    job_id: str,
    target_status: str,
    timeout_seconds: float = 5,
) -> dict:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_seconds:
        payload = manager.get_job_payload(job_id)
        if payload is not None and payload["status"] == target_status:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not reach status '{target_status}' in time.")


def test_fifo_order_and_queue_positions(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(delay_seconds=0.1)
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input1 = test_settings.uploads_dir / "one.wav"
            input2 = test_settings.uploads_dir / "two.wav"
            make_test_wav(input1)
            make_test_wav(input2)

            job1, pos1 = manager.create_job(
                input_path=input1,
                original_filename="one.wav",
                model_id="medium",
                include_timestamps=False,
            )
            job2, pos2 = manager.create_job(
                input_path=input2,
                original_filename="two.wav",
                model_id="medium",
                include_timestamps=False,
            )

            assert pos1 == 1
            assert pos2 == 2

            await wait_for_status(manager, job1.job_id, "done")
            await wait_for_status(manager, job2.job_id, "done")

            assert len(factory.recorder) == 2
            assert factory.recorder[0] == job1.job_id
            assert factory.recorder[1] == job2.job_id
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_job_failure_status(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(fail_model="medium")
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "bad.wav"
            make_test_wav(input_file)

            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="bad.wav",
                model_id="medium",
                include_timestamps=False,
            )

            payload = await wait_for_status(manager, job.job_id, "failed")
            assert payload["error"] is not None
            assert "forced engine failure" in payload["error"]
            assert payload["source_available"] is True
            assert payload["readable_available"] is False
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_cleanup_does_not_remove_old_results(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory()
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "cleanup.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="cleanup.wav",
                model_id="medium",
                include_timestamps=True,
            )

            await wait_for_status(manager, job.job_id, "done")
            stored = manager.get_job(job.job_id)
            assert stored is not None
            assert stored.readable_result_path is not None and stored.readable_result_path.exists()
            sync_path = test_settings.results_dir / f"{job.job_id}.sync.json"
            assert sync_path.exists()
            assert stored.input_path.exists()
            with manager._lock:
                manager._jobs[job.job_id].finished_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

            cleaned = manager.run_cleanup_once()
            assert cleaned == 0
            assert manager.get_job(job.job_id) is not None

            payload = manager.get_job_payload(job.job_id)
            assert payload is not None
            assert payload["status"] == "done"
            assert payload["source_available"] is True
            assert payload["readable_available"] is True
            assert payload["readable_sync_available"] is True
            assert "is_expired" not in payload
            assert "expires_at" not in payload
            assert stored.input_path.exists()
            assert stored.readable_result_path.exists()
            assert sync_path.exists()
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_document_override_roundtrip_prefers_override_path(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory()
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "override.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="override.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, job.job_id, "done")

            initial = manager.get_document_payload(job.job_id, "readable")
            assert initial["edited"] is False

            override_markdown = "# Читабельный текст\n\n## Текст\n\nПользовательский **вариант**.\n"
            saved = manager.save_document_override(job.job_id, "readable", override_markdown)
            assert saved["edited"] is True
            assert saved["updated_at"] is not None

            payload = manager.get_job_payload(job.job_id)
            assert payload is not None
            assert payload["readable_edited"] is True
            assert payload["readable_editor_updated_at"] is not None

            _, effective_path = manager.get_effective_document_path(job.job_id, "readable")
            assert effective_path.name.endswith(".readable.user.md")
            assert effective_path.read_text(encoding="utf-8") == override_markdown

            reset = manager.reset_document_override(job.job_id, "readable")
            assert reset["edited"] is False

            _, restored_path = manager.get_effective_document_path(job.job_id, "readable")
            assert restored_path.name.endswith(".readable.md")
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_waveform_payload_uses_cache_and_invalidates_on_source_change(test_settings) -> None:
    async def scenario() -> None:
        ffmpeg = CountingWaveformFfmpegService()
        manager = JobManager(
            test_settings,
            ffmpeg_service=ffmpeg,
            asr_factory=FakeASRFactory(),
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "waveform-cache.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="waveform-cache.wav",
                model_id="medium",
                include_timestamps=False,
            )
            await wait_for_status(manager, job.job_id, "done")

            first = manager.get_waveform_payload(job.job_id, points=128)
            second = manager.get_waveform_payload(job.job_id, points=128)
            assert first == second
            assert ffmpeg.waveform_calls == 1
            assert len(first["peaks"]) == 128
            assert (test_settings.results_dir / f"{job.job_id}.waveform.json").exists()

            stored = manager.get_job(job.job_id)
            assert stored is not None
            stored.input_path.write_bytes(stored.input_path.read_bytes() + b"x")

            refreshed = manager.get_waveform_payload(job.job_id, points=128)
            assert refreshed["source_size"] != first["source_size"]
            assert ffmpeg.waveform_calls == 2
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_cleanup_keeps_document_overrides(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory()
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "override-cleanup.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="override-cleanup.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, job.job_id, "done")
            manager.save_document_override(
                job.job_id,
                "readable",
                "# Стенограмма\n\n## Текст\n\nПравка.\n",
            )

            stored = manager.get_job(job.job_id)
            assert stored is not None
            assert stored.readable_override_path is not None
            assert stored.readable_override_path.exists()
            with manager._lock:
                manager._jobs[job.job_id].finished_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

            cleaned = manager.run_cleanup_once()
            assert cleaned == 0
            assert stored.readable_override_path.exists()
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_persisted_history_reloads_terminal_jobs(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory()
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "history.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="history.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, job.job_id, "done")
            manager.save_document_override(
                job.job_id,
                "readable",
                "# Р§РёС‚Р°Р±РµР»СЊРЅС‹Р№ С‚РµРєСЃС‚\n\n## РўРµРєСЃС‚\n\nРСЃС‚РѕСЂРёСЏ.\n",
            )
        finally:
            await manager.shutdown()

        reloaded_manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=FakeASRFactory(),
        )
        payload = reloaded_manager.get_job_payload(job.job_id)
        assert payload is not None
        assert payload["status"] == "done"
        assert payload["readable_available"] is True
        assert payload["readable_edited"] is True

    asyncio.run(scenario())


def test_retry_creates_independent_job(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory()
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "retry.wav"
            make_test_wav(input_file)

            original, _ = manager.create_job(
                input_path=input_file,
                original_filename="retry.wav",
                model_id="medium",
                include_timestamps=False,
            )
            await wait_for_status(manager, original.job_id, "done")

            retried, queue_position = manager.retry_job(job_id=original.job_id)
            assert queue_position == 1
            assert retried.retry_of_job_id == original.job_id
            assert retried.job_id != original.job_id

            retried_payload = await wait_for_status(manager, retried.job_id, "done")
            assert retried_payload["retry_of_job_id"] == original.job_id
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_delete_processing_job_rejected(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(delay_seconds=0.5)
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "delete_processing.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="delete_processing.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, job.job_id, "processing")
            try:
                manager.delete_job(job.job_id)
                raise AssertionError("delete_job should fail for processing state")
            except JobStateError:
                pass
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_cancel_processing_job_marks_job_cancelled(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(delay_seconds=0.5)
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input_file = test_settings.uploads_dir / "cancel_processing.wav"
            make_test_wav(input_file)
            job, _ = manager.create_job(
                input_path=input_file,
                original_filename="cancel_processing.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, job.job_id, "processing")
            manager.cancel_job(job.job_id)

            payload = await wait_for_status(manager, job.job_id, "cancelled")
            assert payload["error"] == "Job cancelled by user."
            assert payload["source_available"] is True
            assert payload["readable_available"] is False

            retried, queue_position = manager.retry_job(job_id=job.job_id)
            assert queue_position == 1
            assert retried.retry_of_job_id == job.job_id
            await wait_for_status(manager, retried.job_id, "done")
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_cancel_rejected_for_queued_job(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(delay_seconds=0.4)
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input1 = test_settings.uploads_dir / "queued_cancel_one.wav"
            input2 = test_settings.uploads_dir / "queued_cancel_two.wav"
            make_test_wav(input1)
            make_test_wav(input2)

            first, _ = manager.create_job(
                input_path=input1,
                original_filename="queued_cancel_one.wav",
                model_id="medium",
                include_timestamps=False,
            )
            second, _ = manager.create_job(
                input_path=input2,
                original_filename="queued_cancel_two.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, first.job_id, "processing")
            try:
                manager.cancel_job(second.job_id)
                raise AssertionError("cancel_job should fail for queued state")
            except JobStateError:
                pass
        finally:
            await manager.shutdown()

    asyncio.run(scenario())


def test_cancelled_job_allows_next_queued_job_to_start(test_settings) -> None:
    async def scenario() -> None:
        factory = FakeASRFactory(delay_seconds=0.45)
        manager = JobManager(
            test_settings,
            ffmpeg_service=FakeFfmpegService(),
            asr_factory=factory,
        )
        await manager.start()
        try:
            input1 = test_settings.uploads_dir / "cancel_chain_one.wav"
            input2 = test_settings.uploads_dir / "cancel_chain_two.wav"
            make_test_wav(input1)
            make_test_wav(input2)

            first, _ = manager.create_job(
                input_path=input1,
                original_filename="cancel_chain_one.wav",
                model_id="medium",
                include_timestamps=False,
            )
            second, _ = manager.create_job(
                input_path=input2,
                original_filename="cancel_chain_two.wav",
                model_id="medium",
                include_timestamps=False,
            )

            await wait_for_status(manager, first.job_id, "processing")
            manager.cancel_job(first.job_id)

            await wait_for_status(manager, first.job_id, "cancelled")
            await wait_for_status(manager, second.job_id, "done")
        finally:
            await manager.shutdown()

    asyncio.run(scenario())
