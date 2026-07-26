from __future__ import annotations

from pathlib import Path
from array import array
import math
import os
import subprocess
import sys
import time
import wave

from app.services.asr_base import CancelEvent, JobCancelledError


class FfmpegService:
    def __init__(self, ffmpeg_path: Path) -> None:
        self.ffmpeg_path = Path(ffmpeg_path)

    def is_available(self) -> bool:
        return self.ffmpeg_path.exists()

    def ensure_available(self) -> None:
        if not self.ffmpeg_path.exists():
            raise RuntimeError(
                f"ffmpeg не найден по пути '{self.ffmpeg_path}'. "
                "Добавьте ffmpeg.exe в папку bin/."
            )

    def _windows_subprocess_kwargs(self) -> dict:
        if os.name != "nt":
            return {}

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        return {
            "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
            "startupinfo": startupinfo,
        }

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    def convert_to_wav(
        self,
        input_path: Path,
        output_path: Path,
        cancel_event: CancelEvent | None = None,
    ) -> float:
        self.ensure_available()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            str(self.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(output_path),
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **self._windows_subprocess_kwargs(),
        )

        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    self._stop_process(process)
                    raise JobCancelledError("Job cancelled by user.")

                return_code = process.poll()
                if return_code is not None:
                    break
                time.sleep(0.1)

            _, stderr = process.communicate()
        finally:
            if process.poll() is None:
                self._stop_process(process)

        if process.returncode != 0:
            message = (stderr or "").strip() or "unknown ffmpeg error"
            raise RuntimeError(f"ffmpeg conversion failed: {message}")
        return self.get_wav_duration(output_path)

    def extract_waveform(self, input_path: Path, *, points: int = 900) -> dict:
        self.ensure_available()
        point_count = max(1, int(points))
        command = [
            str(self.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "1000",
            "-f",
            "s16le",
            "pipe:1",
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **self._windows_subprocess_kwargs(),
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            message = (stderr or b"").decode("utf-8", errors="replace").strip() or "unknown ffmpeg error"
            raise RuntimeError(f"ffmpeg waveform extraction failed: {message}")

        samples = array("h")
        even_length = len(stdout) - (len(stdout) % 2)
        if even_length > 0:
            samples.frombytes(stdout[:even_length])
            if sys.byteorder != "little":
                samples.byteswap()

        peaks: list[float] = []
        total = len(samples)
        if total == 0:
            peaks = [0.0] * point_count
        else:
            for index in range(point_count):
                start = math.floor(index * total / point_count)
                end = math.floor((index + 1) * total / point_count)
                if end <= start:
                    peaks.append(0.0)
                    continue
                bucket = samples[start:end]
                peaks.append(min(max(max(abs(value) for value in bucket) / 32768.0, 0.0), 1.0))

        return {
            "points": point_count,
            "peaks": peaks,
            "duration_seconds": total / 1000.0 if total else 0.0,
        }

    def extract_player_audio(self, input_path: Path, output_path: Path) -> float:
        self.ensure_available()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-f",
            "wav",
            str(output_path),
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **self._windows_subprocess_kwargs(),
        )
        _, stderr = process.communicate()
        if process.returncode != 0:
            message = (stderr or "").strip() or "unknown ffmpeg error"
            raise RuntimeError(f"ffmpeg player audio extraction failed: {message}")
        return self.get_wav_duration(output_path)

    @staticmethod
    def get_wav_duration(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
        return frames / float(rate) if rate else 0.0
