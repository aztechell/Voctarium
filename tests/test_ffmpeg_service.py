from __future__ import annotations

from threading import Event

import pytest

from app.services import ffmpeg_service as ffmpeg_module
from app.services.asr_base import JobCancelledError
from app.services.ffmpeg_service import FfmpegService
from tests.conftest import make_test_wav


def test_ffmpeg_uses_hidden_subprocess_on_windows(monkeypatch, tmp_path) -> None:
    service = FfmpegService(tmp_path / "ffmpeg.exe")
    service.ffmpeg_path.write_text("stub", encoding="utf-8")

    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    make_test_wav(input_path, duration_seconds=0.25)

    captured: dict = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured.update(kwargs)
            make_test_wav(output_path, duration_seconds=0.25)
            self.returncode = 0

        def poll(self):
            return self.returncode

        def communicate(self):
            return "", ""

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr("app.services.ffmpeg_service.subprocess.Popen", FakePopen)

    duration = service.convert_to_wav(input_path, output_path)

    assert duration > 0
    assert captured["command"][0] == str(service.ffmpeg_path)
    assert captured["creationflags"] == getattr(ffmpeg_module.subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["startupinfo"] is not None


def test_ffmpeg_cancel_stops_running_process(monkeypatch, tmp_path) -> None:
    service = FfmpegService(tmp_path / "ffmpeg.exe")
    service.ffmpeg_path.write_text("stub", encoding="utf-8")

    input_path = tmp_path / "input.wav"
    output_path = tmp_path / "output.wav"
    make_test_wav(input_path, duration_seconds=0.25)

    captured = {"terminated": False}

    class FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured.update(kwargs)
            self.returncode = None

        def poll(self):
            return self.returncode

        def communicate(self):
            return "", ""

        def wait(self, timeout=None):
            self.returncode = self.returncode if self.returncode is not None else -15
            return self.returncode

        def terminate(self):
            captured["terminated"] = True
            self.returncode = -15

        def kill(self):
            captured["killed"] = True
            self.returncode = -9

    monkeypatch.setattr("app.services.ffmpeg_service.subprocess.Popen", FakePopen)

    cancel_event = Event()
    cancel_event.set()

    with pytest.raises(JobCancelledError):
        service.convert_to_wav(input_path, output_path, cancel_event=cancel_event)

    assert captured["terminated"] is True
