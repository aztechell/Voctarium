from __future__ import annotations

from pathlib import Path
import types

import numpy as np

from app.services.asr_faster_whisper import FasterWhisperEngine
from tests.conftest import make_test_wav


def test_faster_whisper_transcribe_uses_loaded_pcm_audio(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "normalized.wav"
    make_test_wav(audio_path, duration_seconds=0.25)

    captured: dict = {}

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            captured["audio"] = audio
            captured["kwargs"] = kwargs
            segment = types.SimpleNamespace(start=0.0, end=0.8, text="привет")
            return iter([segment]), None

    engine = FasterWhisperEngine()
    engine._model = FakeModel()
    monkeypatch.setattr(engine, "_ensure_model", lambda: None)

    segments = engine.transcribe(audio_path, "ru")

    assert len(segments) == 1
    assert segments[0].text == "привет"
    assert isinstance(captured["audio"], np.ndarray)
    assert captured["audio"].dtype == np.float32
    assert captured["kwargs"]["language"] == "ru"
