from __future__ import annotations

from importlib.util import find_spec

from app.config import Settings
from app.model_manager import FasterWhisperModelManager
from app.services.asr_base import ASREngine
from app.services.asr_faster_whisper import FasterWhisperEngine


class ASRFactory:
    def __init__(self, settings: Settings, model_manager: FasterWhisperModelManager) -> None:
        self.settings = settings
        self.model_manager = model_manager
        self._instances: dict[str, ASREngine] = {}

    def get(self, model_id: str) -> ASREngine:
        resolved_model_id = self.model_manager.ensure_model_available(model_id)
        instance = self._instances.get(resolved_model_id)
        if instance is not None:
            return instance

        instance = FasterWhisperEngine(
            model_name=self.model_manager.resolve_model_source(resolved_model_id),
            device=self.settings.faster_whisper_device,
        )
        self._instances[resolved_model_id] = instance
        return instance

    def readiness(self) -> dict:
        return {
            "faster_whisper": {
                "installed": find_spec("faster_whisper") is not None,
                "active_model": self.model_manager.active_model_id(),
                "installed_models": self.model_manager.installed_model_ids(),
                "device": self.settings.faster_whisper_device,
            },
        }

