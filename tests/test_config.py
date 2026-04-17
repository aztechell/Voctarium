from __future__ import annotations

from pathlib import Path
import sys

from app.config import Settings


def test_from_env_uses_runtime_and_resource_roots_from_env(monkeypatch, tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    resource_root = tmp_path / "resources"
    monkeypatch.setenv("VOCTARIUM_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("VOCTARIUM_RESOURCE_ROOT", str(resource_root))

    settings = Settings.from_env()

    assert settings.runtime_root == runtime_root
    assert settings.resource_root == resource_root
    assert settings.project_root == runtime_root
    assert settings.storage_dir == runtime_root / "storage"
    assert settings.bin_dir == runtime_root / "bin"
    assert settings.models_dir == runtime_root / "models"


def test_from_env_frozen_mode_uses_executable_and_meipass(monkeypatch, tmp_path: Path) -> None:
    exe_dir = tmp_path / "desktop"
    exe_dir.mkdir(parents=True, exist_ok=True)
    fake_exe = exe_dir / "Voctarium.exe"
    fake_exe.write_text("stub", encoding="utf-8")
    meipass = tmp_path / "bundle"
    meipass.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv("VOCTARIUM_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("VOCTARIUM_RESOURCE_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe), raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    settings = Settings.from_env()

    assert settings.runtime_root == exe_dir
    assert settings.resource_root == meipass
    assert settings.project_root == exe_dir

