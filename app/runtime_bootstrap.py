from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Callable
from urllib.request import Request, urlopen
import zipfile


ML_RUNTIME_VERSION = "0.3.0"
ML_RUNTIME_ASSET_NAME = f"Voctarium-v{ML_RUNTIME_VERSION}-ml-runtime.zip"
ML_RUNTIME_URL = (
    "https://github.com/aztechell/Voctarium/releases/download/"
    f"v{ML_RUNTIME_VERSION}/{ML_RUNTIME_ASSET_NAME}"
)
ML_RUNTIME_MARKER = f".voctarium-ml-runtime-{ML_RUNTIME_VERSION}.json"
REQUIRED_RUNTIME_PATHS = (
    "torch/__init__.py",
    "transformers/__init__.py",
    "nvidia/cublas/bin",
    "nvidia/cudnn/bin",
)

ProgressCallback = Callable[[int, int | None], None]


class RuntimeBootstrapError(RuntimeError):
    """Raised when optional ML runtime components cannot be installed."""


def _frozen_internal_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return None
    return Path(meipass).resolve()


def _frozen_runtime_root() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve().parent


def ml_runtime_ready(internal_dir: Path) -> bool:
    root = Path(internal_dir)
    marker = root / ML_RUNTIME_MARKER
    return marker.is_file() and all((root / relative).exists() for relative in REQUIRED_RUNTIME_PATHS)


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    resolved_destination = destination.resolve()
    for member in archive.infolist():
        member_path = (resolved_destination / member.filename).resolve()
        try:
            member_path.relative_to(resolved_destination)
        except ValueError as exc:
            raise RuntimeBootstrapError(
                f"Unsafe path in ML runtime archive: {member.filename}"
            ) from exc
    archive.extractall(resolved_destination)


def ensure_ml_runtime(
    *,
    internal_dir: Path | None = None,
    runtime_root: Path | None = None,
    asset_url: str = ML_RUNTIME_URL,
    progress_callback: ProgressCallback | None = None,
) -> bool:
    target_internal = Path(internal_dir).resolve() if internal_dir else _frozen_internal_dir()
    target_runtime = Path(runtime_root).resolve() if runtime_root else _frozen_runtime_root()
    if target_internal is None or target_runtime is None:
        return False
    if ml_runtime_ready(target_internal):
        return False

    bootstrap_dir = target_runtime / "storage" / "bootstrap"
    bootstrap_dir.mkdir(parents=True, exist_ok=True)
    archive_path = bootstrap_dir / ML_RUNTIME_ASSET_NAME
    partial_path = archive_path.with_suffix(archive_path.suffix + ".download")

    request = Request(asset_url, headers={"User-Agent": "Voctarium-runtime-bootstrap"})
    try:
        with urlopen(request, timeout=120) as response, partial_path.open("wb") as output:
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else None
            downloaded = 0
            while True:
                chunk = response.read(4 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if progress_callback is not None:
                    progress_callback(downloaded, total)
        partial_path.replace(archive_path)

        with zipfile.ZipFile(archive_path) as archive:
            _safe_extract(archive, target_internal)

        missing = [
            relative for relative in REQUIRED_RUNTIME_PATHS if not (target_internal / relative).exists()
        ]
        if missing:
            raise RuntimeBootstrapError(
                "ML runtime archive is incomplete: " + ", ".join(missing)
            )

        marker_payload = {
            "version": ML_RUNTIME_VERSION,
            "asset": ML_RUNTIME_ASSET_NAME,
        }
        (target_internal / ML_RUNTIME_MARKER).write_text(
            json.dumps(marker_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        raise RuntimeBootstrapError(f"Cannot install ML runtime: {exc}") from exc
    finally:
        try:
            partial_path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            archive_path.unlink(missing_ok=True)
        except OSError:
            pass
