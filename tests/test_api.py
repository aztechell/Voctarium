from __future__ import annotations

from datetime import datetime, timezone
import time

from fastapi.testclient import TestClient

import app.main as main_module
from app.job_manager import JobManager
from app.main import create_app
from tests.conftest import FakeASRFactory, FakeFfmpegService, make_test_wav


def wait_until_final(client: TestClient, job_id: str, timeout_seconds: float = 8) -> dict:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_seconds:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"done", "failed", "cancelled"}:
            return payload
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} was not completed in time.")


def test_dashboard_and_result_routes(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "page.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        dashboard_response = client.get("/")
        assert dashboard_response.status_code == 200
        assert 'id="dashboard-root"' in dashboard_response.text
        assert 'id="settings-btn"' in dashboard_response.text
        assert 'id="settings-modal"' in dashboard_response.text
        assert "preview-panel" not in dashboard_response.text

        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("page.wav", handle, "audio/wav")},
                data={"include_timestamps": "true"},
            )
        job_id = create_response.json()["job_id"]
        wait_until_final(client, job_id)

        result_response = client.get(f"/jobs/{job_id}")
        assert result_response.status_code == 200
        assert 'id="result-root"' in result_response.text
        assert f'data-job-id="{job_id}"' in result_response.text
        assert 'id="view-toggle-btn"' in result_response.text
        assert 'id="reader-controls-panel"' in result_response.text
        assert 'id="editor-save-btn"' in result_response.text
        assert 'id="reader-justify-left-btn"' in result_response.text
        assert 'id="reader-justify-full-btn"' in result_response.text
        assert 'id="reader-justify-hyphen-btn"' in result_response.text
        assert 'id="editor-findbar"' in result_response.text
        assert 'id="back-link"' in result_response.text
        assert 'id="settings-modal"' not in result_response.text
        assert 'id="settings-btn"' not in result_response.text
        assert 'id="lang-toggle"' not in result_response.text
        assert 'id="theme-toggle"' not in result_response.text
        assert 'id="retry-btn"' not in result_response.text

        missing_response = client.get("/jobs/missing-job-id")
        assert missing_response.status_code == 404
        assert 'id="result-root"' in missing_response.text
        assert 'data-job-exists="false"' in missing_response.text


def test_api_job_lifecycle_and_preview(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "input.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("input.wav", handle, "audio/wav")},
                data={"include_timestamps": "true"},
            )
        assert create_response.status_code == 200

        created = create_response.json()
        job_id = created["job_id"]
        assert created["status"] == "queued"
        assert created["queue_position"] == 1

        final_payload = wait_until_final(client, job_id)
        assert final_payload["status"] == "done"
        assert final_payload["progress_percent"] == 100
        assert final_payload["source_available"] is True
        assert final_payload["readable_available"] is True
        assert "is_expired" not in final_payload
        assert "expires_at" not in final_payload
        assert final_payload["original_filename"] == "input.wav"
        assert final_payload["model_id"] == "medium"

        list_response = client.get("/api/jobs?limit=10")
        assert list_response.status_code == 200
        list_payload = list_response.json()
        assert list_payload["total"] >= 1
        assert any(item["job_id"] == job_id for item in list_payload["items"])

        readable_response = client.get(f"/api/jobs/{job_id}/readable.md")
        assert readable_response.status_code == 200
        assert "text/markdown" in readable_response.headers["content-type"]
        assert "Читабельный текст" in readable_response.text

        readable_pdf_response = client.get(
            f"/api/jobs/{job_id}/readable.pdf"
            "?font_size_px=20&line_height_mode=relaxed&align_mode=left&paragraph_gap=true&content_width_percent=80"
        )
        assert readable_pdf_response.status_code == 200
        assert "application/pdf" in readable_pdf_response.headers["content-type"]
        assert readable_pdf_response.content.startswith(b"%PDF")

        readable_preview_response = client.get(f"/api/jobs/{job_id}/readable.preview")
        assert readable_preview_response.status_code == 200
        assert '<article class="md-preview">' in readable_preview_response.text


def test_document_endpoints_override_preview_and_exports(test_settings, tmp_path, monkeypatch) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "editable.wav"
    make_test_wav(input_file)
    edited_markdown = "# Читабельный текст\n\n## Текст\n\nНовый **текст**.\n"
    captured_pdf: dict[str, object] = {}

    def fake_render_markdown_pdf(markdown_text: str, **kwargs) -> bytes:
        captured_pdf["markdown_text"] = markdown_text
        captured_pdf.update(kwargs)
        return b"%PDF-test\n"

    monkeypatch.setattr(main_module, "render_markdown_pdf", fake_render_markdown_pdf)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("editable.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )
        job_id = create_response.json()["job_id"]
        wait_until_final(client, job_id)

        initial_document = client.get(f"/api/jobs/{job_id}/documents/readable")
        assert initial_document.status_code == 200
        initial_payload = initial_document.json()
        assert initial_payload["variant"] == "readable"
        assert initial_payload["edited"] is False
        assert initial_payload["base_available"] is True

        update_response = client.put(
            f"/api/jobs/{job_id}/documents/readable",
            json={"markdown": edited_markdown},
        )
        assert update_response.status_code == 200
        updated_payload = update_response.json()
        assert updated_payload["edited"] is True
        assert updated_payload["updated_at"] is not None
        assert "Новый **текст**." in updated_payload["markdown"]

        job_payload = client.get(f"/api/jobs/{job_id}").json()
        assert job_payload["readable_edited"] is True
        assert job_payload["readable_editor_updated_at"] is not None

        readable_md_response = client.get(f"/api/jobs/{job_id}/readable.md")
        assert readable_md_response.status_code == 200
        assert "Новый **текст**." in readable_md_response.text

        readable_preview_response = client.get(f"/api/jobs/{job_id}/readable.preview")
        assert readable_preview_response.status_code == 200
        assert "<strong>текст</strong>" in readable_preview_response.text

        readable_pdf_response = client.get(
            f"/api/jobs/{job_id}/readable.pdf"
            "?font_size_px=20&line_height_mode=relaxed&align_mode=left&paragraph_gap=true&content_width_percent=80"
        )
        assert readable_pdf_response.status_code == 200
        assert readable_pdf_response.content == b"%PDF-test\n"
        assert "Новый **текст**." in str(captured_pdf["markdown_text"])
        assert captured_pdf["fallback_title"] == "editable.wav"
        assert captured_pdf["font_size_px"] == 20
        assert captured_pdf["line_height_mode"] == "relaxed"
        assert captured_pdf["align_mode"] == "left"
        assert captured_pdf["paragraph_gap"] is True
        assert captured_pdf["content_width_percent"] == 80

        reset_response = client.delete(f"/api/jobs/{job_id}/documents/readable")
        assert reset_response.status_code == 200
        reset_payload = reset_response.json()
        assert reset_payload["edited"] is False
        assert reset_payload["updated_at"] is None

        restored_md_response = client.get(f"/api/jobs/{job_id}/readable.md")
        assert restored_md_response.status_code == 200
        assert "Новый **текст**." not in restored_md_response.text


def test_api_retry_and_delete(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "retry-source.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("retry-source.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )
        assert create_response.status_code == 200
        original_id = create_response.json()["job_id"]
        wait_until_final(client, original_id)

        retry_response = client.post(f"/api/jobs/{original_id}/retry", json={"include_timestamps": True})
        assert retry_response.status_code == 200
        retry_payload = retry_response.json()
        retried_id = retry_payload["job_id"]
        assert retry_payload["retry_of_job_id"] == original_id
        assert retried_id != original_id

        retried_final = wait_until_final(client, retried_id)
        assert retried_final["status"] == "done"
        assert retried_final["engine"] == "faster_whisper"
        assert retried_final["model_id"] == "medium"
        assert retried_final["include_timestamps"] is True

        delete_response = client.delete(f"/api/jobs/{retried_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted"] is True

        after_delete = client.get(f"/api/jobs/{retried_id}")
        assert after_delete.status_code == 404


def test_old_job_keeps_results_and_retry(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "persisted.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("persisted.wav", handle, "audio/wav")},
                data={"include_timestamps": "true"},
            )
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        wait_until_final(client, job_id)
        with manager._lock:
            manager._jobs[job_id].finished_at = datetime(2000, 1, 1, tzinfo=timezone.utc)

        assert manager.run_cleanup_once() == 0

        payload = client.get(f"/api/jobs/{job_id}").json()
        assert payload["status"] == "done"
        assert payload["source_available"] is True
        assert payload["readable_available"] is True
        assert "is_expired" not in payload
        assert "expires_at" not in payload

        retry_response = client.post(f"/api/jobs/{job_id}/retry", json={})
        assert retry_response.status_code == 200

        readable_md_response = client.get(f"/api/jobs/{job_id}/readable.md")
        assert readable_md_response.status_code == 200

        readable_preview_response = client.get(f"/api/jobs/{job_id}/readable.preview")
        assert readable_preview_response.status_code == 200

        readable_pdf_response = client.get(f"/api/jobs/{job_id}/readable.pdf")
        assert readable_pdf_response.status_code == 200

        readable_document_response = client.get(f"/api/jobs/{job_id}/documents/readable")
        assert readable_document_response.status_code == 200

        update_document_response = client.put(
            f"/api/jobs/{job_id}/documents/readable",
            json={"markdown": "# Читабельный текст\n\n## Текст\n\nТест.\n"},
        )
        assert update_document_response.status_code == 200

        reset_document_response = client.delete(f"/api/jobs/{job_id}/documents/readable")
        assert reset_document_response.status_code == 200


def test_health_degraded_without_ffmpeg(test_settings) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(available=False),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["worker_running"] is True
        assert payload["ffmpeg_available"] is False


def test_api_cancel_processing_job_and_continue_queue(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(delay_seconds=0.5),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input1 = tmp_path / "cancel-first.wav"
    input2 = tmp_path / "cancel-second.wav"
    make_test_wav(input1)
    make_test_wav(input2)

    with TestClient(app) as client:
        with input1.open("rb") as handle:
            first_response = client.post(
                "/api/jobs",
                files={"file": ("cancel-first.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )
        with input2.open("rb") as handle:
            second_response = client.post(
                "/api/jobs",
                files={"file": ("cancel-second.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )

        first_job_id = first_response.json()["job_id"]
        second_job_id = second_response.json()["job_id"]

        started = time.perf_counter()
        while time.perf_counter() - started < 8:
            payload = client.get(f"/api/jobs/{first_job_id}").json()
            if payload["status"] == "processing":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("First job did not enter processing state in time.")

        queued_cancel = client.post(f"/api/jobs/{second_job_id}/cancel")
        assert queued_cancel.status_code == 409

        cancel_response = client.post(f"/api/jobs/{first_job_id}/cancel")
        assert cancel_response.status_code == 200

        cancelled_payload = wait_until_final(client, first_job_id)
        assert cancelled_payload["status"] == "cancelled"
        assert cancelled_payload["source_available"] is True
        assert cancelled_payload["readable_available"] is False

        cancelled_result = client.get(f"/api/jobs/{first_job_id}/readable.md")
        assert cancelled_result.status_code == 409

        second_final = wait_until_final(client, second_job_id)
        assert second_final["status"] == "done"

        retry_response = client.post(f"/api/jobs/{first_job_id}/retry", json={})
        assert retry_response.status_code == 200
        retry_payload = retry_response.json()
        retried_final = wait_until_final(client, retry_payload["job_id"])
        assert retried_final["status"] == "done"


def test_document_update_rejected_for_processing_job(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(delay_seconds=0.5),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    input_file = tmp_path / "processing-edit.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("processing-edit.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )
        job_id = create_response.json()["job_id"]

        started = time.perf_counter()
        while time.perf_counter() - started < 5:
            payload = client.get(f"/api/jobs/{job_id}").json()
            if payload["status"] == "processing":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Job did not enter processing state in time.")

        update_response = client.put(
            f"/api/jobs/{job_id}/documents/readable",
            json={"markdown": "# Стенограмма\n\n## Текст\n\nТест.\n"},
        )
        assert update_response.status_code == 409


def test_desktop_settings_api(test_settings) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)

    with TestClient(app) as client:
        initial_response = client.get("/api/settings/desktop")
        assert initial_response.status_code == 200
        assert initial_response.json() == {
            "cleanup_uploads_on_close": True,
            "cleanup_queue_on_close": False,
        }

        update_response = client.put(
            "/api/settings/desktop",
            json={
                "cleanup_uploads_on_close": False,
                "cleanup_queue_on_close": True,
            },
        )
        assert update_response.status_code == 200
        assert update_response.json() == {
            "cleanup_uploads_on_close": False,
            "cleanup_queue_on_close": True,
        }

        follow_up = client.get("/api/settings/desktop")
        assert follow_up.status_code == 200
        assert follow_up.json() == {
            "cleanup_uploads_on_close": False,
            "cleanup_queue_on_close": True,
        }


def test_model_catalog_select_and_delete(test_settings) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)
    manager.model_manager._download_sizes = {
        item["id"]: (index + 1) * 1024
        for index, item in enumerate(manager.model_manager.catalog())
    }
    manager.model_manager._ensure_download_sizes = lambda: None

    small_dir = test_settings.models_dir / "faster-whisper-small"
    small_dir.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as client:
        list_response = client.get("/api/models/faster-whisper")
        assert list_response.status_code == 200
        payload = list_response.json()
        rows = {item["id"]: item for item in payload["items"]}
        assert payload["active_model_id"] == "medium"
        assert rows["medium"]["installed"] is True
        assert rows["small"]["installed"] is True
        assert rows["tiny"]["download_size_bytes"] is not None
        assert rows["tiny"]["downloaded_bytes"] >= 0
        assert rows["tiny"]["progress_percent"] >= 0

        select_response = client.post(
            "/api/models/faster-whisper/select",
            json={"model_id": "small"},
        )
        assert select_response.status_code == 200
        assert select_response.json() == {"id": "small", "active": True}

        delete_response = client.delete("/api/models/faster-whisper/medium")
        assert delete_response.status_code == 200
        assert delete_response.json() == {"deleted": True, "id": "medium", "active_model_id": "small"}


def test_delete_model_blocked_while_job_is_using_it(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(delay_seconds=0.5),
    )
    app = create_app(settings=test_settings, job_manager=manager)
    manager.model_manager._download_sizes = {
        item["id"]: (index + 1) * 1024
        for index, item in enumerate(manager.model_manager.catalog())
    }
    manager.model_manager._ensure_download_sizes = lambda: None

    small_dir = test_settings.models_dir / "faster-whisper-small"
    small_dir.mkdir(parents=True, exist_ok=True)
    input_file = tmp_path / "locked-model.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        select_response = client.post(
            "/api/models/faster-whisper/select",
            json={"model_id": "small"},
        )
        assert select_response.status_code == 200

        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("locked-model.wav", handle, "audio/wav")},
                data={"model_id": "medium", "include_timestamps": "false"},
            )
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]

        started = time.perf_counter()
        while time.perf_counter() - started < 8:
            payload = client.get(f"/api/jobs/{job_id}").json()
            if payload["status"] == "processing":
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Job did not enter processing state in time.")

        delete_response = client.delete("/api/models/faster-whisper/medium")
        assert delete_response.status_code == 409
        assert "queued or processing jobs" in delete_response.json()["detail"]

        client.post(f"/api/jobs/{job_id}/cancel")
        wait_until_final(client, job_id)


def test_retry_fails_when_original_model_was_removed(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)
    manager.model_manager._download_sizes = {
        item["id"]: (index + 1) * 1024
        for index, item in enumerate(manager.model_manager.catalog())
    }
    manager.model_manager._ensure_download_sizes = lambda: None

    small_dir = test_settings.models_dir / "faster-whisper-small"
    small_dir.mkdir(parents=True, exist_ok=True)
    input_file = tmp_path / "removed-model.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("removed-model.wav", handle, "audio/wav")},
                data={"model_id": "medium", "include_timestamps": "false"},
            )
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]
        wait_until_final(client, job_id)

        select_response = client.post(
            "/api/models/faster-whisper/select",
            json={"model_id": "small"},
        )
        assert select_response.status_code == 200

        delete_response = client.delete("/api/models/faster-whisper/medium")
        assert delete_response.status_code == 200

        retry_response = client.post(f"/api/jobs/{job_id}/retry", json={})
        assert retry_response.status_code == 409
        assert "unavailable for retry" in retry_response.json()["detail"]


def test_delete_active_model_clears_active_and_blocks_new_jobs(test_settings, tmp_path) -> None:
    manager = JobManager(
        test_settings,
        ffmpeg_service=FakeFfmpegService(),
        asr_factory=FakeASRFactory(),
    )
    app = create_app(settings=test_settings, job_manager=manager)
    manager.model_manager._download_sizes = {
        item["id"]: (index + 1) * 1024
        for index, item in enumerate(manager.model_manager.catalog())
    }
    manager.model_manager._ensure_download_sizes = lambda: None

    input_file = tmp_path / "no-active.wav"
    make_test_wav(input_file)

    with TestClient(app) as client:
        delete_response = client.delete("/api/models/faster-whisper/medium")
        assert delete_response.status_code == 200
        assert delete_response.json() == {"deleted": True, "id": "medium", "active_model_id": None}

        list_response = client.get("/api/models/faster-whisper")
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["active_model_id"] is None

        with input_file.open("rb") as handle:
            create_response = client.post(
                "/api/jobs",
                files={"file": ("no-active.wav", handle, "audio/wav")},
                data={"include_timestamps": "false"},
            )
        assert create_response.status_code == 409
