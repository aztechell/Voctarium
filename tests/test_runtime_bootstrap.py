from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from app.runtime_bootstrap import (
    ML_RUNTIME_MARKER,
    REQUIRED_RUNTIME_PATHS,
    ensure_ml_runtime,
    ml_runtime_ready,
)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._stream = BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def _runtime_zip() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for relative in REQUIRED_RUNTIME_PATHS:
            path = Path(relative)
            if path.suffix:
                archive.writestr(path.as_posix(), "# test\n")
            else:
                archive.writestr((path / ".keep").as_posix(), "")
    return buffer.getvalue()


def test_ensure_ml_runtime_downloads_and_marks_install(monkeypatch, tmp_path) -> None:
    payload = _runtime_zip()
    progress: list[tuple[int, int | None]] = []
    statuses: list[str] = []
    monkeypatch.setattr(
        "app.runtime_bootstrap.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    installed = ensure_ml_runtime(
        internal_dir=tmp_path / "_internal",
        runtime_root=tmp_path / "runtime",
        asset_url="https://example.invalid/runtime.zip",
        progress_callback=lambda downloaded, total: progress.append((downloaded, total)),
        status_callback=statuses.append,
    )

    assert installed is True
    assert ml_runtime_ready(tmp_path / "_internal") is True
    assert (tmp_path / "_internal" / ML_RUNTIME_MARKER).is_file()
    assert progress[-1] == (len(payload), len(payload))
    assert statuses == ["downloading", "extracting", "ready"]


def test_ensure_ml_runtime_skips_existing_install(tmp_path) -> None:
    internal = tmp_path / "_internal"
    for relative in REQUIRED_RUNTIME_PATHS:
        path = internal / relative
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# test\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
    (internal / ML_RUNTIME_MARKER).write_text("{}\n", encoding="utf-8")

    assert ensure_ml_runtime(internal_dir=internal, runtime_root=tmp_path / "runtime") is False
