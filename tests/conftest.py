from __future__ import annotations

from pathlib import Path
import shutil
from threading import Event
import time
import wave

import pytest

from app.config import Settings
from app.services.asr_base import JobCancelledError
from app.types import TranscriptSegment


def make_test_wav(path: Path, duration_seconds: float = 0.5, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


class FakeFfmpegService:
    def __init__(self, available: bool = True, *, delay_seconds: float = 0.0) -> None:
        self.available = available
        self.delay_seconds = delay_seconds

    def is_available(self) -> bool:
        return self.available

    def convert_to_wav(
        self,
        input_path: Path,
        output_path: Path,
        cancel_event: Event | None = None,
    ) -> float:
        if self.delay_seconds > 0:
            started = time.perf_counter()
            while time.perf_counter() - started < self.delay_seconds:
                if cancel_event is not None and cancel_event.is_set():
                    raise JobCancelledError("Job cancelled by user.")
                time.sleep(0.01)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(input_path, output_path)
        return 5.0

    def extract_waveform(self, input_path: Path, *, points: int = 900) -> dict:
        del input_path
        return {
            "points": points,
            "peaks": [0.25 if index % 2 else 0.75 for index in range(points)],
            "duration_seconds": 5.0,
        }

    def extract_player_audio(self, input_path: Path, output_path: Path) -> float:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(input_path, output_path)
        return 5.0


class FakeEngine:
    def __init__(self, recorder: list[str], *, fail: bool = False, delay_seconds: float = 0.0) -> None:
        self._recorder = recorder
        self._fail = fail
        self._delay_seconds = delay_seconds

    def transcribe(
        self,
        wav_path: Path,
        language: str,
        progress_callback=None,
        cancel_event: Event | None = None,
    ) -> list[TranscriptSegment]:
        del language
        if self._fail:
            raise RuntimeError("forced engine failure")

        self._recorder.append(Path(wav_path).stem)
        if progress_callback is not None:
            progress_callback(1.0)
            progress_callback(5.0)
        if self._delay_seconds > 0:
            started = time.perf_counter()
            while time.perf_counter() - started < self._delay_seconds:
                if cancel_event is not None and cancel_event.is_set():
                    raise JobCancelledError("Job cancelled by user.")
                time.sleep(0.01)

        return [
            TranscriptSegment(start=0.0, end=1.0, text="привет"),
            TranscriptSegment(start=1.0, end=2.0, text="мир"),
        ]


class FakeASRFactory:
    def __init__(
        self,
        *,
        fail_model: str | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.recorder: list[str] = []
        self.model_requests: list[str] = []
        self._fail_model = fail_model
        self._delay_seconds = delay_seconds

    def get(self, model_id: str):
        self.model_requests.append(model_id)
        return FakeEngine(
            self.recorder,
            fail=self._fail_model == model_id,
            delay_seconds=self._delay_seconds,
        )

    def readiness(self) -> dict:
        return {
            "faster_whisper": {
                "installed": True,
                "active_model": "medium",
                "installed_models": ["medium"],
                "device": "cuda",
            },
        }


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    source_root = Path(__file__).resolve().parent.parent
    runtime_root = tmp_path / "runtime"
    settings = Settings(
        project_root=runtime_root,
        runtime_root=runtime_root,
        resource_root=source_root,
        storage_dir=runtime_root / "storage",
        uploads_dir=runtime_root / "storage" / "uploads",
        work_dir=runtime_root / "storage" / "work",
        results_dir=runtime_root / "storage" / "results",
        app_state_path=runtime_root / "storage" / "app_state.json",
        bin_dir=runtime_root / "bin",
        ffmpeg_path=runtime_root / "bin" / "ffmpeg.exe",
        models_dir=runtime_root / "models",
        rupunct_model_path=runtime_root / "models" / "rupunct-big",
        readable_punct_device="cpu",
        cleanup_interval_seconds=1,
    )
    settings.ensure_directories()
    (settings.models_dir / "faster-whisper-medium").mkdir(parents=True, exist_ok=True)
    return settings
