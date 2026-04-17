from __future__ import annotations

import socket
import sys
import types
from typing import Any

import pytest

import app.desktop_launcher as desktop_launcher
from app.desktop_launcher import (
    DesktopSaveBridge,
    DesktopLaunchError,
    StartupSplash,
    UvicornRunner,
    find_available_port,
    purge_session_storage,
    run_desktop,
    wait_until_server_ready,
)


def test_find_available_port_prefers_requested_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        preferred_port = int(sock.getsockname()[1])

    selected = find_available_port(host="127.0.0.1", preferred_port=preferred_port)
    assert selected == preferred_port


def test_find_available_port_falls_back_if_occupied() -> None:
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = int(occupied.getsockname()[1])
    try:
        selected = find_available_port(host="127.0.0.1", preferred_port=occupied_port)
        assert selected != occupied_port
        assert selected > 0
    finally:
        occupied.close()


def test_wait_until_server_ready_times_out() -> None:
    with pytest.raises(DesktopLaunchError):
        wait_until_server_ready(
            "http://127.0.0.1:9",
            timeout_seconds=0.3,
            poll_interval_seconds=0.05,
        )


def test_wait_until_server_ready_fails_if_server_stops() -> None:
    with pytest.raises(DesktopLaunchError, match="stopped during startup"):
        wait_until_server_ready(
            "http://127.0.0.1:9",
            timeout_seconds=2.0,
            poll_interval_seconds=0.05,
            server_is_alive=lambda: False,
        )


def test_uvicorn_runner_disables_default_log_config() -> None:
    class FakeConfig:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.log_config = kwargs.get("log_config")

    class FakeServer:
        def __init__(self, config):
            self.config = config

        def run(self):  # pragma: no cover - test does not start thread.
            return None

    fake_uvicorn = types.SimpleNamespace(Config=FakeConfig, Server=FakeServer)
    module_name = "uvicorn"

    import sys

    previous = sys.modules.get(module_name)
    sys.modules[module_name] = fake_uvicorn
    try:
        runner = UvicornRunner(host="127.0.0.1", port=8020, app_path="unit-test-app")
        assert runner._config.log_config is None
    finally:
        if previous is None:
            del sys.modules[module_name]
        else:
            sys.modules[module_name] = previous


def test_server_process_runner_command_for_source(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    runner = desktop_launcher.ServerProcessRunner(host="127.0.0.1", port=8020)
    assert runner._command() == [
        sys.executable,
        "-m",
        "app.desktop_entry",
        "--server",
        "--host",
        "127.0.0.1",
        "--port",
        "8020",
    ]


def test_server_process_runner_command_for_frozen(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    runner = desktop_launcher.ServerProcessRunner(host="127.0.0.1", port=8020)
    assert runner._command() == [
        sys.executable,
        "--server",
        "--host",
        "127.0.0.1",
        "--port",
        "8020",
    ]


def test_startup_splash_fallback_without_tkinter(monkeypatch) -> None:
    splash = StartupSplash()

    def _raise_missing() -> Any:
        raise ModuleNotFoundError("tkinter missing")

    monkeypatch.setattr(splash, "_load_tkinter", _raise_missing)
    assert splash.start() is False
    splash.close()  # Should be safe no-op.


def test_run_desktop_closes_splash_when_startup_fails(monkeypatch) -> None:
    class FakeRunner:
        def __init__(self, **kwargs):
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        def stop(self, timeout_seconds: float = 10.0) -> None:
            self.stopped = True

        @property
        def is_alive(self) -> bool:
            return self.started and not self.stopped

    class FakeSplash:
        def __init__(self):
            self.started = False
            self.closed = False

        def start(self) -> bool:
            self.started = True
            return True

        def close(self) -> None:
            self.closed = True

    fake_splash = FakeSplash()

    def fake_wait(*args, **kwargs) -> None:
        raise DesktopLaunchError("boom")

    monkeypatch.setattr(desktop_launcher, "wait_until_server_ready", fake_wait)

    with pytest.raises(DesktopLaunchError, match="boom"):
        run_desktop(
            server_factory=FakeRunner,
            startup_splash_factory=lambda: fake_splash,
        )

    assert fake_splash.started is True
    assert fake_splash.closed is True


def test_purge_session_storage_recreates_runtime_dirs(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    uploads = runtime_root / "storage" / "uploads"
    work = runtime_root / "storage" / "work"
    results = runtime_root / "storage" / "results"
    history = runtime_root / "storage" / "job_history.json"

    for directory in (uploads, work, results):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "artifact.txt").write_text("x", encoding="utf-8")
    history.write_text("{}", encoding="utf-8")

    processed = purge_session_storage(
        runtime_root,
        cleanup_uploads_on_close=True,
        cleanup_queue_on_close=True,
    )

    assert uploads in processed
    assert work in processed
    assert results in processed
    assert history in processed
    assert uploads.exists() and not any(uploads.iterdir())
    assert work.exists() and not any(work.iterdir())
    assert results.exists() and not any(results.iterdir())
    assert not history.exists()


def test_purge_session_storage_respects_persisted_desktop_settings(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    storage = runtime_root / "storage"
    uploads = storage / "uploads"
    work = storage / "work"
    results = storage / "results"
    history = storage / "job_history.json"
    app_state = storage / "app_state.json"

    for directory in (uploads, work, results):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "artifact.txt").write_text("x", encoding="utf-8")
    history.write_text("{}", encoding="utf-8")
    app_state.write_text(
        '{"desktop_settings":{"cleanup_uploads_on_close":true,"cleanup_queue_on_close":false}}',
        encoding="utf-8",
    )

    processed = purge_session_storage(runtime_root)

    assert uploads in processed
    assert work in processed
    assert results not in processed
    assert history not in processed
    assert uploads.exists() and not any(uploads.iterdir())
    assert work.exists() and not any(work.iterdir())
    assert results.exists() and any(results.iterdir())
    assert history.exists()


def test_run_desktop_configures_webview_window(monkeypatch, tmp_path) -> None:
    class FakeRunner:
        def __init__(self, **kwargs):
            self.started = False
            self.stopped = False

        def start(self) -> None:
            self.started = True

        def stop(self, timeout_seconds: float = 10.0) -> None:
            self.stopped = True

        @property
        def is_alive(self) -> bool:
            return self.started and not self.stopped

    class FakeSplash:
        def __init__(self):
            self.messages: list[str] = []
            self.closed = False

        def start(self) -> bool:
            return True

        def update_message(self, message: str) -> None:
            self.messages.append(message)

        def close(self) -> None:
            self.closed = True

    class FakeEvent:
        def __init__(self):
            self.handlers: list[Any] = []

        def __iadd__(self, handler):
            self.handlers.append(handler)
            return self

    class FakeWindow:
        def __init__(self):
            self.on_top = True
            self.events = types.SimpleNamespace(closed=FakeEvent(), shown=FakeEvent())

    captured: dict[str, Any] = {}
    fake_window = FakeWindow()
    fake_splash = FakeSplash()

    def fake_create_window(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return fake_window

    def fake_start(**kwargs):
        captured["start_kwargs"] = kwargs
        assert fake_splash.closed is False
        for handler in fake_window.events.shown.handlers:
            handler()

    fake_webview = types.SimpleNamespace(
        create_window=fake_create_window,
        start=fake_start,
    )
    fake_localization = types.SimpleNamespace(
        original_localization={
            "global.quitConfirmation": "Do you really want to quit?",
            "global.quit": "Quit",
            "global.cancel": "Cancel",
        }
    )

    monkeypatch.setattr(desktop_launcher, "wait_until_server_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(desktop_launcher, "detect_desktop_language", lambda: "en")
    monkeypatch.setenv("VOCTARIUM_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setitem(sys.modules, "webview", fake_webview)
    monkeypatch.setitem(sys.modules, "webview.localization", fake_localization)

    result = run_desktop(
        server_factory=FakeRunner,
        startup_splash_factory=lambda: fake_splash,
    )

    assert result == 0
    assert isinstance(captured["kwargs"]["js_api"], DesktopSaveBridge)
    assert captured["kwargs"]["maximized"] is True
    assert captured["kwargs"]["focus"] is True
    assert captured["kwargs"]["on_top"] is True
    assert captured["kwargs"]["confirm_close"] is True
    assert captured["kwargs"]["background_color"] == desktop_launcher.WINDOW_BACKGROUND
    assert captured["kwargs"]["localization"]["global.quitConfirmation"].startswith("Close Voctarium")
    assert fake_window.on_top is False
    assert fake_splash.messages == [
        "Starting Voctarium...",
        "Preparing local server...",
        "Opening desktop window...",
    ]
    assert fake_splash.closed is True


def test_desktop_save_bridge_saves_markdown_to_selected_path(monkeypatch, tmp_path) -> None:
    target = tmp_path / "saved.readable.md"

    class FakeWindow:
        def create_file_dialog(self, *args, **kwargs):
            return str(target)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"# Readable text\n"

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(SAVE_DIALOG=30))
    monkeypatch.setattr(desktop_launcher, "urlopen", lambda *args, **kwargs: FakeResponse())

    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")
    bridge.attach_window(FakeWindow())

    payload = bridge.save_markdown("job-1", "readable", "input.readable.md")

    assert payload["ok"] is True
    assert payload["cancelled"] is False
    assert target.read_text(encoding="utf-8") == "# Readable text\n"


def test_desktop_save_bridge_saves_pdf_to_selected_path(monkeypatch, tmp_path) -> None:
    target = tmp_path / "saved.readable.pdf"
    captured: dict[str, str] = {}

    class FakeWindow:
        def create_file_dialog(self, *args, **kwargs):
            return str(target)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"%PDF-1.7\nmock\n"

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(SAVE_DIALOG=30))

    def fake_urlopen(url, *args, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setattr(desktop_launcher, "urlopen", fake_urlopen)

    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")
    bridge.attach_window(FakeWindow())

    payload = bridge.save_pdf(
        "job-1",
        "readable",
        "input.readable.pdf",
        {
            "font_size_px": 20,
            "line_height_mode": "relaxed",
            "align_mode": "left",
            "paragraph_gap": True,
            "content_width_percent": 80,
        },
    )

    assert payload["ok"] is True
    assert payload["cancelled"] is False
    assert target.read_bytes() == b"%PDF-1.7\nmock\n"
    assert "font_size_px=20" in captured["url"]
    assert "line_height_mode=relaxed" in captured["url"]
    assert "align_mode=left" in captured["url"]


def test_desktop_save_bridge_handles_cancelled_dialog(monkeypatch) -> None:
    class FakeWindow:
        def create_file_dialog(self, *args, **kwargs):
            return None

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(SAVE_DIALOG=30))

    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")
    bridge.attach_window(FakeWindow())

    payload = bridge.save_markdown("job-1", "result", "input.result.md")

    assert payload == {"ok": False, "cancelled": True}


def test_desktop_save_bridge_uses_private_window_field() -> None:
    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")

    assert hasattr(bridge, "_window")
    assert hasattr(bridge, "_base_url")
    assert not hasattr(bridge, "window")
    assert not hasattr(bridge, "base_url")


def test_desktop_save_bridge_resolves_window_from_webview_windows(monkeypatch, tmp_path) -> None:
    target = tmp_path / "saved.result.md"

    class FakeWindow:
        def create_file_dialog(self, *args, **kwargs):
            return str(target)

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"# Result\n"

    fake_window = FakeWindow()
    monkeypatch.setitem(
        sys.modules,
        "webview",
        types.SimpleNamespace(SAVE_DIALOG=30, windows=[fake_window]),
    )
    monkeypatch.setattr(desktop_launcher, "urlopen", lambda *args, **kwargs: FakeResponse())

    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")
    payload = bridge.save_markdown("job-1", "result", "input.result.md")

    assert payload["ok"] is True
    assert target.read_text(encoding="utf-8") == "# Result\n"


def test_desktop_save_bridge_status_reports_window_state(monkeypatch) -> None:
    class FakeWindow:
        pass

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(windows=[]))
    bridge = DesktopSaveBridge(base_url="http://127.0.0.1:8000")

    status_without_window = bridge.bridge_status()
    assert status_without_window["ok"] is True
    assert status_without_window["window_attached"] is False
    assert status_without_window["window_resolved"] is False
    assert status_without_window["has_save_pdf"] is True

    bridge.attach_window(FakeWindow())
    status_with_window = bridge.bridge_status()
    assert status_with_window["ok"] is True
    assert status_with_window["window_attached"] is True
    assert status_with_window["window_resolved"] is True
    assert status_with_window["has_save_pdf"] is True
