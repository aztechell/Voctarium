from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys


def _runtime_root() -> Path:
    env_root = os.getenv("VOCTARIUM_RUNTIME_ROOT")
    if env_root:
        return Path(env_root)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def write_runtime_trace(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    log_path = _runtime_root() / "voctarium_runtime.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] Voctarium Runtime Trace\n{message}\n\n")
    except Exception:
        pass
