from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import threading
from typing import Any

import requests

from app.config import Settings
from app.runtime_logging import write_runtime_trace


MODEL_CATALOG: tuple[dict[str, str], ...] = (
    {"id": "tiny", "label": "tiny", "repo_id": "Systran/faster-whisper-tiny"},
    {"id": "base", "label": "base", "repo_id": "Systran/faster-whisper-base"},
    {"id": "small", "label": "small", "repo_id": "Systran/faster-whisper-small"},
    {"id": "medium", "label": "medium", "repo_id": "Systran/faster-whisper-medium"},
    {"id": "large-v3", "label": "large-v3", "repo_id": "Systran/faster-whisper-large-v3"},
    {"id": "turbo", "label": "turbo", "repo_id": "Systran/faster-whisper-turbo"},
)
MODEL_IDS = {item["id"] for item in MODEL_CATALOG}
DEFAULT_DESKTOP_SETTINGS: dict[str, bool] = {
    "cleanup_uploads_on_close": False,
    "cleanup_queue_on_close": False,
}


class ModelManagerError(Exception):
    """Base exception for faster-whisper model management."""


class ModelNotFoundError(ModelManagerError):
    """Raised when model id is unknown or missing."""


class ModelStateError(ModelManagerError):
    """Raised when model action is not allowed."""


@dataclass(slots=True)
class _DownloadState:
    downloading: bool = False
    error: str | None = None
    download_size_bytes: int | None = None
    downloaded_bytes: int = 0
    progress_percent: int = 0


def _normalize_model_id(value: str | None) -> str:
    raw = (value or "").strip()
    if raw in MODEL_IDS:
        return raw

    path_name = Path(raw).name.lower()
    if path_name.startswith("faster-whisper-"):
        candidate = path_name.removeprefix("faster-whisper-")
        if candidate in MODEL_IDS:
            return candidate

    raise ModelNotFoundError(f"Unknown faster-whisper model '{value}'.")


class FasterWhisperModelManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.RLock()
        self._downloads: dict[str, _DownloadState] = {}
        self._download_sizes: dict[str, int | None] = {}
        self._active_download_model_id: str | None = None
        initial_state = self._load_state_payload()
        self._active_model_id = self._load_active_model_id(initial_state)
        self._desktop_settings = self._load_desktop_settings(initial_state)
        self._ensure_active_model_consistency()

    def _state_payload(self) -> dict[str, object]:
        return {
            "active_faster_whisper_model": self._active_model_id,
            "desktop_settings": dict(self._desktop_settings),
        }

    def _load_state_payload(self) -> dict[str, Any]:
        try:
            if not self.settings.app_state_path.exists():
                return {}
            payload = json.loads(self.settings.app_state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_active_model_id(self, payload: dict[str, Any] | None = None) -> str | None:
        default_model = _normalize_model_id(self.settings.faster_whisper_model)
        try:
            payload = payload if payload is not None else self._load_state_payload()
            selected = payload.get("active_faster_whisper_model", default_model)
            if selected is None:
                return None
            return _normalize_model_id(selected)
        except (OSError, json.JSONDecodeError, ModelNotFoundError):
            return default_model

    def _load_desktop_settings(self, payload: dict[str, Any] | None = None) -> dict[str, bool]:
        resolved = dict(DEFAULT_DESKTOP_SETTINGS)
        source = payload if payload is not None else self._load_state_payload()
        raw = source.get("desktop_settings")
        if not isinstance(raw, dict):
            return resolved

        for key, default in DEFAULT_DESKTOP_SETTINGS.items():
            value = raw.get(key, default)
            resolved[key] = bool(value)
        return resolved

    def _save_state(self) -> None:
        self.settings.app_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings.app_state_path.write_text(
            json.dumps(self._state_payload(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _ensure_active_model_consistency(self) -> None:
        installed = self.installed_model_ids()
        if self._active_model_id is None:
            return
        if self._active_model_id in installed:
            return
        fallback = "medium" if "medium" in installed else (installed[0] if installed else None)
        if self._active_model_id != fallback:
            self._active_model_id = fallback
            self._save_state()

    @staticmethod
    def catalog() -> tuple[dict[str, str], ...]:
        return MODEL_CATALOG

    def installed_model_ids(self) -> list[str]:
        return [item["id"] for item in MODEL_CATALOG if self.model_dir(item["id"]).exists()]

    def active_model_id(self) -> str | None:
        with self._lock:
            self._ensure_active_model_consistency()
            return self._active_model_id

    def desktop_settings(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._desktop_settings)

    def update_desktop_settings(
        self,
        *,
        cleanup_uploads_on_close: bool,
        cleanup_queue_on_close: bool,
    ) -> dict[str, bool]:
        with self._lock:
            self._desktop_settings = {
                "cleanup_uploads_on_close": bool(cleanup_uploads_on_close),
                "cleanup_queue_on_close": bool(cleanup_queue_on_close),
            }
            self._save_state()
            return dict(self._desktop_settings)

    def model_dir(self, model_id: str) -> Path:
        normalized = _normalize_model_id(model_id)
        return self.settings.models_dir / f"faster-whisper-{normalized}"

    def resolve_model_source(self, model_id: str) -> str:
        model_path = self.model_dir(model_id)
        if not model_path.exists():
            raise ModelStateError(f"Model '{model_id}' is not installed.")
        return str(model_path)

    def ensure_model_available(self, model_id: str | None) -> str:
        if not model_id:
            raise ModelStateError("No faster-whisper model is selected.")
        normalized = _normalize_model_id(model_id)
        if not self.model_dir(normalized).exists():
            raise ModelStateError(f"Model '{normalized}' is not installed.")
        return normalized

    def _fetch_model_manifest(self, model_id: str) -> tuple[str, list[dict[str, Any]], int | None]:
        from huggingface_hub import HfApi

        normalized = _normalize_model_id(model_id)
        repo_id = next(item["repo_id"] for item in MODEL_CATALOG if item["id"] == normalized)
        info = HfApi().model_info(repo_id, files_metadata=True)

        files: list[dict[str, Any]] = []
        total_size = 0
        has_known_size = False
        for sibling in info.siblings or []:
            relative_path = getattr(sibling, "rfilename", None)
            if not relative_path:
                continue
            raw_size = getattr(sibling, "size", None)
            size = int(raw_size) if isinstance(raw_size, int) and raw_size >= 0 else None
            if size is not None:
                total_size += size
                has_known_size = True
            files.append({"rfilename": relative_path, "size": size})

        return repo_id, files, total_size if has_known_size else None

    def _ensure_download_sizes(self) -> None:
        missing = [item["id"] for item in MODEL_CATALOG if item["id"] not in self._download_sizes]
        if not missing:
            return

        for model_id in missing:
            try:
                _, _, total_size = self._fetch_model_manifest(model_id)
            except Exception as exc:
                total_size = None
                write_runtime_trace(f"model-manager: metadata fetch failed {model_id}: {exc}")
            with self._lock:
                self._download_sizes[model_id] = total_size
                state = self._downloads.setdefault(model_id, _DownloadState())
                if state.download_size_bytes is None:
                    state.download_size_bytes = total_size

    def _set_download_progress(self, model_id: str, *, downloaded_bytes: int, total_size: int | None) -> None:
        with self._lock:
            state = self._downloads.setdefault(model_id, _DownloadState())
            state.download_size_bytes = total_size
            state.downloaded_bytes = max(0, int(downloaded_bytes))
            if total_size and total_size > 0:
                state.progress_percent = max(0, min(100, int((state.downloaded_bytes / total_size) * 100)))
            else:
                state.progress_percent = 100 if not state.downloading else 0

    def _download_model_files(
        self,
        *,
        model_id: str,
        repo_id: str,
        files: list[dict[str, Any]],
        target_dir: Path,
        total_size: int | None,
    ) -> None:
        from huggingface_hub import hf_hub_url

        downloaded_bytes = 0
        self._set_download_progress(model_id, downloaded_bytes=0, total_size=total_size)

        for file_info in files:
            relative_path = str(file_info["rfilename"])
            destination = target_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)

            response = requests.get(
                hf_hub_url(repo_id=repo_id, filename=relative_path),
                stream=True,
                timeout=(10.0, 120.0),
            )
            response.raise_for_status()
            with response:
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded_bytes += len(chunk)
                        self._set_download_progress(
                            model_id,
                            downloaded_bytes=downloaded_bytes,
                            total_size=total_size,
                        )

    def list_models(self) -> list[dict[str, object]]:
        self._ensure_download_sizes()
        with self._lock:
            active = self.active_model_id()
            active_download = self._active_download_model_id
            rows: list[dict[str, object]] = []
            for item in MODEL_CATALOG:
                model_id = item["id"]
                state = self._downloads.get(model_id) or _DownloadState()
                installed = self.model_dir(model_id).exists()
                downloading = active_download == model_id and state.downloading
                rows.append(
                    {
                        "id": model_id,
                        "label": item["label"],
                        "repo_id": item["repo_id"],
                        "download_size_bytes": state.download_size_bytes if state.download_size_bytes is not None else self._download_sizes.get(model_id),
                        "downloaded_bytes": state.downloaded_bytes,
                        "progress_percent": state.progress_percent,
                        "installed": installed,
                        "active": model_id == active,
                        "downloading": downloading,
                        "deletable": installed and not downloading,
                        "error": state.error,
                    }
                )
            return rows

    def select_model(self, model_id: str) -> dict[str, object]:
        normalized = self.ensure_model_available(model_id)
        with self._lock:
            self._active_model_id = normalized
            self._save_state()
        return {"id": normalized, "active": True}

    def delete_model(self, model_id: str) -> dict[str, object]:
        normalized = _normalize_model_id(model_id)
        target = self.model_dir(normalized)
        with self._lock:
            if self._active_download_model_id == normalized:
                raise ModelStateError("Model download is still in progress.")
        if not target.exists():
            raise ModelNotFoundError(f"Model '{normalized}' is not installed.")
        shutil.rmtree(target)
        with self._lock:
            if normalized == self._active_model_id:
                self._active_model_id = None
                self._save_state()
            self._downloads[normalized] = _DownloadState(download_size_bytes=self._download_sizes.get(normalized))
        return {"deleted": True, "id": normalized, "active_model_id": self._active_model_id}

    def install_model(self, model_id: str) -> dict[str, object]:
        normalized = _normalize_model_id(model_id)
        target = self.model_dir(normalized)
        if target.exists():
            return {"started": False, "id": normalized, "installed": True}

        with self._lock:
            if self._active_download_model_id and self._active_download_model_id != normalized:
                raise ModelStateError("Another model download is already in progress.")

            state = self._downloads.setdefault(normalized, _DownloadState())
            if state.downloading:
                raise ModelStateError("Model download is already in progress.")

            state.downloading = True
            state.error = None
            state.downloaded_bytes = 0
            state.progress_percent = 0
            if normalized in self._download_sizes:
                state.download_size_bytes = self._download_sizes[normalized]
            self._active_download_model_id = normalized

        thread = threading.Thread(
            target=self._install_worker,
            args=(normalized,),
            daemon=True,
            name=f"fw-model-install-{normalized}",
        )
        thread.start()
        return {"started": True, "id": normalized}

    def _install_worker(self, model_id: str) -> None:
        target = self.model_dir(model_id)
        temp_target = target.with_name(f"{target.name}.download")
        try:
            repo_id, files, total_size = self._fetch_model_manifest(model_id)
            with self._lock:
                self._download_sizes[model_id] = total_size
                state = self._downloads.setdefault(model_id, _DownloadState())
                state.download_size_bytes = total_size
                state.downloaded_bytes = 0
                state.progress_percent = 0
            if temp_target.exists():
                shutil.rmtree(temp_target)
            temp_target.parent.mkdir(parents=True, exist_ok=True)
            write_runtime_trace(f"model-manager: download start {model_id}")
            self._download_model_files(
                model_id=model_id,
                repo_id=repo_id,
                files=files,
                target_dir=temp_target,
                total_size=total_size,
            )
            if target.exists():
                shutil.rmtree(target)
            temp_target.replace(target)
            write_runtime_trace(f"model-manager: download done {model_id}")
            with self._lock:
                state = self._downloads.setdefault(model_id, _DownloadState())
                state.downloading = False
                state.error = None
                state.downloaded_bytes = state.download_size_bytes or state.downloaded_bytes
                state.progress_percent = 100
                self._active_download_model_id = None
                if self._active_model_id not in self.installed_model_ids():
                    self._active_model_id = model_id
                    self._save_state()
        except Exception as exc:
            write_runtime_trace(f"model-manager: download failed {model_id}: {exc}")
            try:
                if temp_target.exists():
                    shutil.rmtree(temp_target)
            except OSError:
                pass
            with self._lock:
                state = self._downloads.setdefault(model_id, _DownloadState())
                state.downloading = False
                state.error = str(exc)
                state.progress_percent = 0
                self._active_download_model_id = None
