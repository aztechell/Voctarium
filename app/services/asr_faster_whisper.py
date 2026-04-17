from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
import wave

import numpy as np

from app.runtime_logging import write_runtime_trace
from app.services.asr_base import CancelEvent, JobCancelledError, ProgressCallback
from app.types import TranscriptSegment


_WINDOWS_DLL_HANDLES: list[object] = []
_VAD_MISSING_ASSET_MARKERS = (
    "silero_encoder_v5.onnx",
    "silero_decoder_v5.onnx",
    "no_suchfile",
    "file doesn't exist",
)


def _configure_windows_cuda_dll_path() -> None:
    if os.name != "nt":
        return

    candidates: list[Path] = []
    for entry in sys.path:
        if not entry:
            continue
        base = Path(entry)
        candidates.append(base / "nvidia" / "cublas" / "bin")
        candidates.append(base / "nvidia" / "cudnn" / "bin")

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if not candidate.exists():
            continue

        path_value = str(candidate)
        current_path = os.environ.get("PATH", "")
        parts = current_path.lower().split(";")
        if path_value.lower() not in parts:
            os.environ["PATH"] = path_value + ";" + current_path if current_path else path_value

        if hasattr(os, "add_dll_directory"):
            # Keep handles alive for process lifetime to preserve DLL lookup scope.
            _WINDOWS_DLL_HANDLES.append(os.add_dll_directory(path_value))


def _is_vad_asset_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _VAD_MISSING_ASSET_MARKERS)


class FasterWhisperEngine:
    def __init__(
        self,
        model_name: str = "medium",
        device: str = "cuda",
        compute_type: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type or ("float16" if device == "cuda" else "int8")
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        write_runtime_trace("faster-whisper: configuring runtime paths")
        _configure_windows_cuda_dll_path()
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper не установлен. Установите зависимости из requirements.txt."
            ) from exc

        try:
            write_runtime_trace(
                f"faster-whisper: loading model={self.model_name} device={self.device}"
            )
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            write_runtime_trace("faster-whisper: model loaded")
        except Exception as exc:  # pragma: no cover - зависит от среды/драйвера.
            raise RuntimeError(
                f"Не удалось загрузить faster-whisper модель '{self.model_name}' "
                f"на устройстве '{self.device}': {exc}"
            ) from exc

    def _transcribe_once(
        self,
        audio: np.ndarray,
        language: str,
        vad_filter: bool,
    ) -> tuple[Any, Any]:
        assert self._model is not None
        return self._model.transcribe(
            audio,
            language=language,
            beam_size=5,
            vad_filter=vad_filter,
        )

    @staticmethod
    def _load_normalized_wav(wav_path: Path) -> np.ndarray:
        write_runtime_trace(f"faster-whisper: loading wav {wav_path}")
        with wave.open(str(wav_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())

        if channels != 1 or sample_width != 2 or sample_rate != 16000:
            raise RuntimeError(
                "Ожидается нормализованный WAV 16kHz mono PCM16. Проверьте ffmpeg-конвертацию."
            )

        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        write_runtime_trace(f"faster-whisper: wav loaded samples={audio.shape[0]}")
        return audio

    def transcribe(
        self,
        wav_path: Path,
        language: str,
        progress_callback: ProgressCallback | None = None,
        cancel_event: CancelEvent | None = None,
    ) -> list[TranscriptSegment]:
        self._ensure_model()
        assert self._model is not None
        audio = self._load_normalized_wav(wav_path)
        write_runtime_trace("faster-whisper: transcribe call start")

        if cancel_event is not None and cancel_event.is_set():
            raise JobCancelledError("Job cancelled by user.")

        try:
            segments_iter, _ = self._transcribe_once(
                audio=audio,
                language=language,
                vad_filter=True,
            )
        except Exception as exc:
            if not _is_vad_asset_missing_error(exc):
                raise RuntimeError(f"Ошибка распознавания faster-whisper: {exc}") from exc

            try:
                write_runtime_trace("faster-whisper: retry without VAD")
                segments_iter, _ = self._transcribe_once(
                    audio=audio,
                    language=language,
                    vad_filter=False,
                )
            except Exception as fallback_exc:
                raise RuntimeError(
                    "Ошибка распознавания faster-whisper (повтор без VAD также не удался): "
                    f"{fallback_exc}"
                ) from fallback_exc

        segments: list[TranscriptSegment] = []
        for segment in segments_iter:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelledError("Job cancelled by user.")

            text = (segment.text or "").strip()
            if not text:
                continue
            start = float(segment.start or 0.0)
            end = float(segment.end or start)
            segments.append(TranscriptSegment(start=start, end=end, text=text))
            if progress_callback is not None:
                progress_callback(end)

        return segments
