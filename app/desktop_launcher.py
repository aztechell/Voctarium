from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import locale
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
from typing import Callable
from urllib.parse import quote, urlencode
from urllib.error import URLError
from urllib.request import urlopen


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
WINDOW_BACKGROUND = "#12161d"
SESSION_STORAGE_SUBDIRS = ("uploads", "work", "results")
DEFAULT_DESKTOP_SETTINGS = {
    "cleanup_uploads_on_close": False,
    "cleanup_queue_on_close": False,
}

_DESKTOP_STRINGS = {
    "ru": {
        "launching": "Запуск Voctarium...",
        "installing_runtime": "Установка компонентов распознавания...",
        "runtime_progress": "Загрузка компонентов: {percent}%",
        "preparing": "Подготовка сервера...",
        "opening": "Открытие окна...",
        "quit_confirmation": "Закрыть Voctarium? Текущая desktop-сессия завершится, а загруженные файлы будут очищены.",
        "quit": "Закрыть",
        "cancel": "Отмена",
    },
    "en": {
        "launching": "Starting Voctarium...",
        "installing_runtime": "Installing speech recognition components...",
        "runtime_progress": "Downloading components: {percent}%",
        "preparing": "Preparing local server...",
        "opening": "Opening desktop window...",
        "quit_confirmation": "Close Voctarium? The current desktop session will end and uploaded files will be cleaned.",
        "quit": "Quit",
        "cancel": "Cancel",
    },
}


class DesktopLaunchError(Exception):
    """Raised when desktop launcher cannot start or run."""


class DesktopSaveBridge:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._window = None

    def attach_window(self, window) -> None:
        self._window = window
        write_runtime_trace("save-markdown: bridge attached")

    def _resolve_window(self):
        if self._window is not None:
            return self._window

        try:
            import webview
        except Exception:
            return None

        windows = getattr(webview, "windows", None)
        if isinstance(windows, (list, tuple)) and windows:
            fallback_window = windows[0]
            self._window = fallback_window
            write_runtime_trace("save-markdown: window resolved from webview.windows[0]")
            return fallback_window
        return None

    def bridge_status(self) -> dict[str, object]:
        resolved_window = self._resolve_window()
        status: dict[str, object] = {
            "window_attached": self._window is not None,
            "window_resolved": resolved_window is not None,
            "has_save_markdown": hasattr(self, "save_markdown"),
            "has_save_pdf": hasattr(self, "save_pdf"),
            "has_play_notification": hasattr(self, "play_notification"),
        }
        try:
            import webview  # noqa: F401
            status["webview_module"] = True
        except Exception:
            status["webview_module"] = False
        write_runtime_trace(f"save-markdown: bridge-status {status}")
        return {"ok": True, **status}

    def save_markdown(self, job_id: str, variant: str, suggested_filename: str) -> dict[str, object]:
        return self._save_remote_file(
            job_id,
            variant,
            suggested_filename,
            file_kind="md",
            file_types=("Markdown (*.md)",),
        )

    def save_pdf(
        self,
        job_id: str,
        variant: str,
        suggested_filename: str,
        export_options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return self._save_remote_file(
            job_id,
            variant,
            suggested_filename,
            file_kind="pdf",
            file_types=("PDF (*.pdf)",),
            export_options=export_options,
        )

    def _save_remote_file(
        self,
        job_id: str,
        variant: str,
        suggested_filename: str,
        *,
        file_kind: str,
        file_types: tuple[str, ...],
        export_options: dict[str, object] | None = None,
    ) -> dict[str, object]:
        window = self._resolve_window()
        if window is None:
            return {"ok": False, "error": "Desktop window is not ready."}

        try:
            import webview
        except Exception:
            return {"ok": False, "error": "pywebview is unavailable."}

        resolved_variant = "readable"
        default_name = _sanitize_save_filename(suggested_filename, resolved_variant, file_kind)
        trace_prefix = f"save-{file_kind}"
        write_runtime_trace(
            f"{trace_prefix}: request job_id={job_id} variant={resolved_variant} suggested={default_name}"
        )
        try:
            selected = window.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_name,
                file_types=file_types,
            )
        except Exception as exc:
            write_runtime_trace(f"{trace_prefix}: dialog failed: {exc}")
            return {"ok": False, "cancelled": False, "error": f"Save dialog failed: {exc}"}

        if not selected:
            write_runtime_trace(f"{trace_prefix}: dialog cancelled")
            return {"ok": False, "cancelled": True}

        if isinstance(selected, str):
            selected_path = selected
        elif isinstance(selected, (list, tuple)):
            selected_path = selected[0] if selected else ""
        elif isinstance(selected, os.PathLike):
            selected_path = os.fspath(selected)
        else:
            selected_path = str(selected) if selected else ""
            write_runtime_trace(
                f"{trace_prefix}: unexpected dialog return type={type(selected)!r}; coerced to {selected_path!r}"
            )
        if not selected_path:
            write_runtime_trace(f"{trace_prefix}: empty selection treated as cancelled")
            return {"ok": False, "cancelled": True}

        target = Path(selected_path).resolve()
        source_url = f"{self._base_url}/api/jobs/{quote(job_id)}/readable.{file_kind}"
        if file_kind == "pdf" and export_options:
            query_payload = {
                "font_size_px": export_options.get("font_size_px"),
                "line_height_mode": export_options.get("line_height_mode"),
                "align_mode": export_options.get("align_mode"),
                "paragraph_gap": export_options.get("paragraph_gap"),
                "content_width_percent": export_options.get("content_width_percent"),
            }
            filtered = {key: value for key, value in query_payload.items() if value is not None}
            if filtered:
                source_url = f"{source_url}?{urlencode(filtered)}"

        try:
            with urlopen(source_url, timeout=60.0) as response:
                status_code = int(response.status) if hasattr(response, "status") else int(response.getcode())
                if status_code != 200:
                    body = response.read().decode("utf-8", errors="replace").strip()
                    message = body or f"HTTP {status_code}"
                    write_runtime_trace(
                        f"{trace_prefix}: source request failed status={status_code} message={message}"
                    )
                    return {"ok": False, "cancelled": False, "error": message}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(response.read())
        except Exception as exc:
            write_runtime_trace(f"{trace_prefix}: write failed path={target}: {exc}")
            return {"ok": False, "cancelled": False, "error": str(exc)}

        write_runtime_trace(f"{trace_prefix}: saved to {target}")
        return {"ok": True, "cancelled": False, "path": str(target)}

    def play_notification(self, kind: str) -> dict[str, object]:
        try:
            if os.name == "nt":
                import winsound

                sound_type = (
                    winsound.MB_ICONEXCLAMATION
                    if kind == "job_attention"
                    else winsound.MB_ICONASTERISK
                )
                winsound.MessageBeep(sound_type)
            else:
                print("\a", end="", flush=True)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}


class StartupSplash:
    def __init__(
        self,
        *,
        title: str = "Voctarium",
        message: str = _DESKTOP_STRINGS["ru"]["launching"],
        width: int = 380,
        height: int = 128,
    ) -> None:
        self.title = title
        self.width = width
        self.height = height
        self._message = message
        self._message_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._close_requested = threading.Event()
        self._failed = False
        self._tk = None

    def _load_tkinter(self):
        import tkinter as tk

        return tk

    def _center_window(self, root) -> None:
        root.update_idletasks()
        x = max((root.winfo_screenwidth() - self.width) // 2, 0)
        y = max((root.winfo_screenheight() - self.height) // 3, 0)
        root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def _get_message(self) -> str:
        with self._message_lock:
            return self._message

    def update_message(self, message: str) -> None:
        with self._message_lock:
            self._message = message

    def _run(self) -> None:
        try:
            tk = self._tk
            if tk is None:
                self._failed = True
                self._started.set()
                return

            root = tk.Tk()
            root.title(self.title)
            root.resizable(False, False)
            root.configure(bg="#11161d")
            root.attributes("-topmost", True)
            root.protocol("WM_DELETE_WINDOW", lambda: None)

            frame = tk.Frame(root, bg="#11161d", padx=18, pady=18)
            frame.pack(fill="both", expand=True)

            accent = tk.Frame(frame, bg="#3aa7b5", width=6)
            accent.pack(side="left", fill="y")

            content = tk.Frame(frame, bg="#11161d", padx=14)
            content.pack(side="left", fill="both", expand=True)

            title_label = tk.Label(
                content,
                text=self.title,
                bg="#11161d",
                fg="#f5f7fb",
                font=("Segoe UI Semibold", 12),
                anchor="w",
            )
            title_label.pack(fill="x")

            message_label = tk.Label(
                content,
                text=self._get_message(),
                bg="#11161d",
                fg="#aeb7c4",
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
                wraplength=self.width - 90,
            )
            message_label.pack(fill="both", expand=True, pady=(10, 0))

            self._center_window(root)
            self._started.set()

            def check_state() -> None:
                if self._close_requested.is_set():
                    root.destroy()
                    return
                message_label.configure(text=self._get_message())
                root.after(80, check_state)

            root.after(80, check_state)
            root.mainloop()
        except Exception:
            self._failed = True
            self._started.set()

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True

        self._started.clear()
        self._close_requested.clear()
        self._failed = False

        try:
            self._tk = self._load_tkinter()
        except Exception:
            return False

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._started.wait(timeout=2.0)
        return self._started.is_set() and not self._failed

    def close(self) -> None:
        self._close_requested.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3.0)



def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True



def find_available_port(host: str = DEFAULT_HOST, preferred_port: int = DEFAULT_PORT) -> int:
    if is_port_available(host, preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])



def wait_until_server_ready(
    base_url: str,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.2,
    server_is_alive: Callable[[], bool] | None = None,
) -> None:
    health_url = f"{base_url}/health"
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server_is_alive is not None and not server_is_alive():
            raise DesktopLaunchError("Background API server stopped during startup.")
        try:
            with urlopen(health_url, timeout=2.0) as response:
                if response.status != 200:
                    time.sleep(poll_interval_seconds)
                    continue
                payload = json.loads(response.read().decode("utf-8"))
                if payload.get("status") in {"ok", "degraded"}:
                    return
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            pass
        time.sleep(poll_interval_seconds)
    raise DesktopLaunchError(f"Server did not become ready in {timeout_seconds} seconds.")



def show_native_error(title: str, message: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"[{title}] {message}")



def _resolve_runtime_root_for_logs() -> Path:
    runtime_root = os.getenv("VOCTARIUM_RUNTIME_ROOT")
    if runtime_root:
        return Path(runtime_root)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()



def _startup_log_path() -> Path:
    return _resolve_runtime_root_for_logs() / "voctarium_startup.log"



def _runtime_log_path() -> Path:
    return _resolve_runtime_root_for_logs() / "voctarium_runtime.log"



def _append_log(log_path: Path, title: str, message: str, details: str | None = None) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [f"[{timestamp}] {title}", message]
    if details:
        lines.append(details.rstrip())
    lines.append("")

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
    except Exception:
        pass



def write_startup_log(title: str, message: str, details: str | None = None) -> None:
    _append_log(_startup_log_path(), title, message, details)



def write_runtime_log(title: str, message: str, details: str | None = None) -> None:
    _append_log(_runtime_log_path(), title, message, details)



def write_startup_trace(message: str) -> None:
    write_startup_log("Voctarium Startup Trace", message)



def write_runtime_trace(message: str) -> None:
    write_runtime_log("Voctarium Runtime Trace", message)



def detect_desktop_language() -> str:
    candidates = [
        os.getenv("VOCTARIUM_UI_LANG"),
        locale.getlocale()[0],
        os.getenv("LANG"),
        os.getenv("LC_ALL"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        normalized = str(candidate).lower()
        if normalized.startswith("ru"):
            return "ru"
        if normalized.startswith("en"):
            return "en"
    return "ru"



def _desktop_string(language: str, key: str) -> str:
    selected = _DESKTOP_STRINGS.get(language, _DESKTOP_STRINGS["ru"])
    return selected[key]


def _sanitize_save_filename(filename: str, variant: str, file_kind: str = "md") -> str:
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", filename or "").strip().strip(".")
    if not cleaned:
        cleaned = "voctarium"
    expected_suffix = f".{file_kind.lower()}"
    if not cleaned.lower().endswith(expected_suffix):
        suffix = f".readable.{file_kind.lower()}"
        stem = re.sub(r"\.[^.]+$", "", cleaned)
        cleaned = f"{stem or 'voctarium'}{suffix}"
    return cleaned



def _set_splash_message(splash: object | None, message: str) -> None:
    if splash is None:
        return
    updater = getattr(splash, "update_message", None)
    if callable(updater):
        updater(message)



def _prepare_runtime_env() -> Path | None:
    runtime_root: Path | None = None
    if getattr(sys, "frozen", False):
        runtime_root = Path(sys.executable).resolve().parent
        os.environ.setdefault("VOCTARIUM_RUNTIME_ROOT", str(runtime_root))
    elif os.getenv("VOCTARIUM_RUNTIME_ROOT"):
        runtime_root = Path(os.environ["VOCTARIUM_RUNTIME_ROOT"]).resolve()

    if runtime_root is None:
        return None

    return runtime_root



def load_desktop_settings(runtime_root: Path | None) -> dict[str, bool]:
    if runtime_root is None:
        return dict(DEFAULT_DESKTOP_SETTINGS)

    app_state_path = runtime_root / "storage" / "app_state.json"
    try:
        if not app_state_path.exists():
            return dict(DEFAULT_DESKTOP_SETTINGS)
        payload = json.loads(app_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_DESKTOP_SETTINGS)

    raw_settings = payload.get("desktop_settings") if isinstance(payload, dict) else None
    if not isinstance(raw_settings, dict):
        return dict(DEFAULT_DESKTOP_SETTINGS)

    return {
        "cleanup_uploads_on_close": bool(
            raw_settings.get(
                "cleanup_uploads_on_close",
                DEFAULT_DESKTOP_SETTINGS["cleanup_uploads_on_close"],
            )
        ),
        "cleanup_queue_on_close": bool(
            raw_settings.get(
                "cleanup_queue_on_close",
                DEFAULT_DESKTOP_SETTINGS["cleanup_queue_on_close"],
            )
        ),
    }


def purge_session_storage(
    runtime_root: Path | None,
    *,
    cleanup_uploads_on_close: bool | None = None,
    cleanup_queue_on_close: bool | None = None,
) -> list[Path]:
    if runtime_root is None:
        return []

    resolved_settings = load_desktop_settings(runtime_root)
    if cleanup_uploads_on_close is not None:
        resolved_settings["cleanup_uploads_on_close"] = bool(cleanup_uploads_on_close)
    if cleanup_queue_on_close is not None:
        resolved_settings["cleanup_queue_on_close"] = bool(cleanup_queue_on_close)

    storage_root = runtime_root / "storage"
    processed: list[Path] = []
    targets: list[Path] = []
    history_path = storage_root / "job_history.json"

    for name in SESSION_STORAGE_SUBDIRS:
        if name in ("uploads", "work") and not resolved_settings["cleanup_uploads_on_close"]:
            continue
        if name == "results" and not resolved_settings["cleanup_queue_on_close"]:
            continue
        targets.append(storage_root / name)

    if resolved_settings["cleanup_queue_on_close"]:
        targets.append(history_path)

    for target in targets:
        try:
            if target.suffix:
                target.unlink(missing_ok=True)
            else:
                if target.exists():
                    shutil.rmtree(target)
                target.mkdir(parents=True, exist_ok=True)
            processed.append(target)
        except OSError as exc:
            write_runtime_log(
                "Voctarium Session Cleanup Warning",
                f"Failed to clean '{target}': {exc}",
            )
    return processed



def _build_webview_localization(language: str) -> dict[str, str]:
    from webview.localization import original_localization

    localization = dict(original_localization)
    localization.update(
        {
            "global.quitConfirmation": _desktop_string(language, "quit_confirmation"),
            "global.quit": _desktop_string(language, "quit"),
            "global.cancel": _desktop_string(language, "cancel"),
        }
    )
    return localization


@dataclass(slots=True)
class UvicornRunner:
    app_path: str = "app.main:app"
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    log_level: str = "warning"
    _config: object = field(init=False, repr=False)
    _server: object = field(init=False, repr=False)
    _thread: threading.Thread = field(init=False, repr=False)

    def _resolve_app_target(self) -> object:
        if self.app_path != "app.main:app":
            return self.app_path
        from app.main import app as fastapi_app

        return fastapi_app

    def __post_init__(self) -> None:
        import uvicorn

        app_target = self._resolve_app_target()
        self._config = uvicorn.Config(
            app_target,
            host=self.host,
            port=self.port,
            log_level=self.log_level,
            access_log=False,
            log_config=None,
            use_colors=False,
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout_seconds: float = 10.0) -> None:
        self._server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=timeout_seconds)

    @property
    def is_alive(self) -> bool:
        return self._thread.is_alive()


@dataclass(slots=True)
class ServerProcessRunner:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    _process: subprocess.Popen | None = field(init=False, default=None, repr=False)
    _stdout_handle: object | None = field(init=False, default=None, repr=False)
    _stderr_handle: object | None = field(init=False, default=None, repr=False)

    def _command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            return [
                sys.executable,
                "--server",
                "--host",
                self.host,
                "--port",
                str(self.port),
            ]

        return [
            sys.executable,
            "-m",
            "app.desktop_entry",
            "--server",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]

    @staticmethod
    def _creation_kwargs() -> dict:
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }

    def start(self) -> None:
        runtime_root = _resolve_runtime_root_for_logs()
        stdout_path = runtime_root / "server.stdout.log"
        stderr_path = runtime_root / "server.stderr.log"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        self._stdout_handle = stdout_path.open("a", encoding="utf-8")
        self._stderr_handle = stderr_path.open("a", encoding="utf-8")
        self._process = subprocess.Popen(
            self._command(),
            stdout=self._stdout_handle,
            stderr=self._stderr_handle,
            **self._creation_kwargs(),
        )

    def stop(self, timeout_seconds: float = 10.0) -> None:
        try:
            if self._process is not None and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    self._process.kill()
        finally:
            for handle in (self._stdout_handle, self._stderr_handle):
                if handle is not None:
                    try:
                        handle.close()
                    except Exception:
                        pass
            self._stdout_handle = None
            self._stderr_handle = None

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None



def run_desktop(
    *,
    host: str = DEFAULT_HOST,
    preferred_port: int = DEFAULT_PORT,
    title: str = "Voctarium STT",
    width: int = 1460,
    height: int = 940,
    min_size: tuple[int, int] = (1040, 720),
    server_factory: Callable[..., object] = ServerProcessRunner,
    startup_splash_factory: Callable[[], StartupSplash] | None = None,
) -> int:
    write_startup_trace("run_desktop: begin")

    language = detect_desktop_language()
    splash = startup_splash_factory() if startup_splash_factory is not None else None
    splash_closed = False

    def close_splash(reason: str) -> None:
        nonlocal splash_closed
        if splash is None or splash_closed:
            return
        splash_closed = True
        write_startup_trace(reason)
        splash.close()

    if splash is not None:
        _set_splash_message(splash, _desktop_string(language, "launching"))
        splash_started = splash.start()
        if splash_started:
            write_startup_trace("startup splash shown")
        else:
            write_startup_trace("startup splash unavailable; continuing without splash")

    runtime_root = _prepare_runtime_env()
    write_startup_trace(
        f"runtime_env prepared; runtime_root={os.getenv('VOCTARIUM_RUNTIME_ROOT', '')}"
    )

    if getattr(sys, "frozen", False):
        from app.runtime_bootstrap import ensure_ml_runtime

        _set_splash_message(splash, _desktop_string(language, "installing_runtime"))

        def update_runtime_progress(downloaded: int, total: int | None) -> None:
            if not total:
                return
            percent = max(0, min(100, int(downloaded * 100 / total)))
            template = _desktop_string(language, "runtime_progress")
            _set_splash_message(splash, template.format(percent=percent))

        ensure_ml_runtime(progress_callback=update_runtime_progress)

    cleaned_start = purge_session_storage(runtime_root)
    if cleaned_start:
        write_runtime_trace(
            "pre-launch cleanup prepared: " + ", ".join(str(path) for path in cleaned_start)
        )

    _set_splash_message(splash, _desktop_string(language, "preparing"))

    port = find_available_port(host=host, preferred_port=preferred_port)
    base_url = f"http://{host}:{port}"
    write_startup_trace(f"selected base_url={base_url}")
    write_startup_trace("creating server runner")
    runner: object | None = None

    try:
        runner = server_factory(host=host, port=port)
        write_startup_trace("server runner created")
        write_startup_trace("starting server runner")
        runner.start()
        write_startup_trace("server runner started; waiting for /health")
        wait_until_server_ready(
            base_url,
            timeout_seconds=45.0,
            server_is_alive=lambda: runner.is_alive,
        )
        write_startup_trace("server /health ready")

        try:
            write_startup_trace("importing webview")
            import webview
        except Exception as exc:
            raise DesktopLaunchError(
                "pywebview is not installed. Install requirements-desktop.txt and rebuild."
            ) from exc

        localization = _build_webview_localization(language)
        _set_splash_message(splash, _desktop_string(language, "opening"))
        save_bridge = DesktopSaveBridge(base_url=base_url)

        write_startup_trace("creating desktop window")
        window = webview.create_window(
            title,
            base_url,
            width=width,
            height=height,
            min_size=min_size,
            maximized=True,
            focus=True,
            on_top=True,
            confirm_close=True,
            localization=localization,
            background_color=WINDOW_BACKGROUND,
            js_api=save_bridge,
        )
        save_bridge.attach_window(window)

        def on_shown() -> None:
            write_startup_trace("desktop window shown")
            try:
                window.on_top = False
                write_runtime_trace("desktop window startup on_top disabled")
            except Exception:
                write_runtime_trace("desktop window startup on_top disable failed")
            close_splash("closing startup splash after window shown")

        def on_closed() -> None:
            write_runtime_trace("desktop window closed")
            if runner is not None:
                runner.stop()

        window.events.shown += on_shown
        window.events.closed += on_closed

        try:
            write_startup_trace("starting webview event loop")
            webview.start(gui="edgechromium", debug=False)
            write_startup_trace("webview event loop exited")
        except Exception as exc:
            raise DesktopLaunchError(
                "Cannot start WebView2 window. Ensure Microsoft Edge WebView2 Runtime is installed."
            ) from exc
    finally:
        close_splash("closing startup splash during cleanup")
        if runner is not None:
            write_startup_trace("stopping uvicorn runner")
            runner.stop()
        cleaned_stop = purge_session_storage(runtime_root)
        if cleaned_stop:
            write_runtime_trace(
                "shutdown cleanup prepared: " + ", ".join(str(path) for path in cleaned_stop)
            )
        write_startup_trace("run_desktop: end")
    return 0



def main() -> int:
    try:
        return run_desktop()
    except DesktopLaunchError as exc:
        write_startup_log("Voctarium Startup Error", str(exc))
        show_native_error("Voctarium Startup Error", str(exc))
    except Exception as exc:  # pragma: no cover - defensive branch
        write_startup_log(
            "Voctarium Fatal Error",
            str(exc),
            details=traceback.format_exc(),
        )
        show_native_error("Voctarium Fatal Error", str(exc))
    return 1
