from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys


@dataclass(slots=True)
class Settings:
    project_root: Path
    runtime_root: Path
    resource_root: Path
    storage_dir: Path
    uploads_dir: Path
    work_dir: Path
    results_dir: Path
    app_state_path: Path
    bin_dir: Path
    ffmpeg_path: Path
    models_dir: Path
    rupunct_model_path: Path
    faster_whisper_model: str = "medium"
    faster_whisper_device: str = "cuda"
    readable_punct_device: str = "cpu"
    cleanup_interval_seconds: int = 300

    @staticmethod
    def detect_runtime_root(project_root: Path | None = None) -> Path:
        env_root = os.getenv("VOCTARIUM_RUNTIME_ROOT")
        if env_root:
            return Path(env_root)
        if project_root is not None:
            return Path(project_root)
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent

    @staticmethod
    def detect_resource_root(runtime_root: Path) -> Path:
        env_root = os.getenv("VOCTARIUM_RESOURCE_ROOT")
        if env_root:
            return Path(env_root)
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                return Path(meipass)
            return runtime_root
        return Path(__file__).resolve().parent.parent

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        runtime_root = cls.detect_runtime_root(project_root)
        resource_root = cls.detect_resource_root(runtime_root)

        storage_dir = Path(os.getenv("VOCTARIUM_STORAGE_DIR", runtime_root / "storage"))
        uploads_dir = storage_dir / "uploads"
        work_dir = storage_dir / "work"
        results_dir = storage_dir / "results"
        app_state_path = storage_dir / "app_state.json"

        bin_dir = runtime_root / "bin"
        ffmpeg_path = Path(os.getenv("VOCTARIUM_FFMPEG_PATH", bin_dir / "ffmpeg.exe"))

        models_dir = runtime_root / "models"
        rupunct_model_path = Path(
            os.getenv("VOCTARIUM_RUPUNCT_MODEL_PATH", models_dir / "rupunct-big")
        )

        return cls(
            project_root=runtime_root,
            runtime_root=runtime_root,
            resource_root=resource_root,
            storage_dir=storage_dir,
            uploads_dir=uploads_dir,
            work_dir=work_dir,
            results_dir=results_dir,
            app_state_path=app_state_path,
            bin_dir=bin_dir,
            ffmpeg_path=ffmpeg_path,
            models_dir=models_dir,
            rupunct_model_path=rupunct_model_path,
            faster_whisper_model=os.getenv("VOCTARIUM_FASTER_WHISPER_MODEL", "medium"),
            faster_whisper_device=os.getenv("VOCTARIUM_FASTER_WHISPER_DEVICE", "cuda"),
            readable_punct_device=os.getenv("VOCTARIUM_READABLE_PUNCT_DEVICE", "cpu"),
            cleanup_interval_seconds=int(os.getenv("VOCTARIUM_CLEANUP_INTERVAL_SECONDS", "300")),
        )

    def ensure_directories(self) -> None:
        directories = (
            self.storage_dir,
            self.uploads_dir,
            self.work_dir,
            self.results_dir,
            self.bin_dir,
            self.models_dir,
        )
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
