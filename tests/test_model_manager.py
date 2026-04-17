from __future__ import annotations

from pathlib import Path
import time

from app.model_manager import FasterWhisperModelManager


def _prime_model_sizes(manager: FasterWhisperModelManager) -> None:
    manager._download_sizes = {item["id"]: (index + 1) * 1024 for index, item in enumerate(manager.catalog())}


def test_model_manager_lists_catalog_and_active_model(test_settings) -> None:
    manager = FasterWhisperModelManager(test_settings)
    _prime_model_sizes(manager)

    rows = {item["id"]: item for item in manager.list_models()}

    assert manager.active_model_id() == "medium"
    assert set(rows) == {"tiny", "base", "small", "medium", "large-v3", "turbo"}
    assert rows["medium"]["installed"] is True
    assert rows["medium"]["active"] is True
    assert rows["medium"]["deletable"] is True
    assert rows["medium"]["download_size_bytes"] is not None
    assert rows["medium"]["downloaded_bytes"] >= 0
    assert rows["medium"]["progress_percent"] >= 0
    assert rows["small"]["installed"] is False
    assert rows["small"]["active"] is False


def test_model_manager_select_and_delete_non_active_model(test_settings) -> None:
    small_dir = test_settings.models_dir / "faster-whisper-small"
    small_dir.mkdir(parents=True, exist_ok=True)

    manager = FasterWhisperModelManager(test_settings)

    selected = manager.select_model("small")
    assert selected == {"id": "small", "active": True}
    assert manager.active_model_id() == "small"

    deleted = manager.delete_model("medium")
    assert deleted == {"deleted": True, "id": "medium", "active_model_id": "small"}
    assert not (test_settings.models_dir / "faster-whisper-medium").exists()


def test_model_manager_install_model_marks_downloaded(test_settings, monkeypatch) -> None:
    manager = FasterWhisperModelManager(test_settings)
    _prime_model_sizes(manager)

    def fake_manifest(model_id: str):
        assert model_id == "tiny"
        return "Systran/faster-whisper-tiny", [{"rfilename": "config.json", "size": 19}], 19

    def fake_download(*, model_id, repo_id, files, target_dir, total_size):
        del model_id, repo_id, files
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text("{}", encoding="utf-8")
        manager._set_download_progress("tiny", downloaded_bytes=19, total_size=total_size)

    monkeypatch.setattr(manager, "_fetch_model_manifest", fake_manifest)
    monkeypatch.setattr(manager, "_download_model_files", fake_download)
    result = manager.install_model("tiny")
    assert result == {"started": True, "id": "tiny"}

    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline:
        rows = {item["id"]: item for item in manager.list_models()}
        if rows["tiny"]["installed"] and not rows["tiny"]["downloading"]:
            break
        time.sleep(0.05)
    else:
        raise AssertionError("tiny model did not finish downloading in time")

    assert (test_settings.models_dir / "faster-whisper-tiny").exists()
    assert rows["tiny"]["installed"] is True
    assert rows["tiny"]["error"] is None
    assert rows["tiny"]["download_size_bytes"] == 19
    assert rows["tiny"]["downloaded_bytes"] == 19
    assert rows["tiny"]["progress_percent"] == 100


def test_model_manager_delete_active_model_clears_active_state(test_settings) -> None:
    manager = FasterWhisperModelManager(test_settings)
    deleted = manager.delete_model("medium")
    assert deleted == {"deleted": True, "id": "medium", "active_model_id": None}
    assert manager.active_model_id() is None
