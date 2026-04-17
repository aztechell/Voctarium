from __future__ import annotations

from pathlib import Path
import os
import subprocess
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

    @staticmethod
    def get_wav_duration(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
        return frames / float(rate) if rate else 0.0
