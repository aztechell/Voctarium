from __future__ import annotations

from app.readable_text import ReadableTextProcessor, build_readable_paragraphs
from app.types import EngineType, TranscriptSegment


class FakePunctuator:
    def punctuate(self, text: str) -> str:
        return text.replace(" итак ", ". Итак ").replace(" важен контекст", " важен контекст.")


class FlakyPunctuator:
    def __init__(self) -> None:
        self.calls = 0

    def punctuate(self, text: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("boom")
        return f"{text}."


class BrokenPunctuator:
    def punctuate(self, text: str) -> str:
        return "??? ?!"


class CommaArtifactPunctuator:
    def punctuate(self, text: str) -> str:
        return "итак,, это важно, . например,, человек думает, ?"


def test_build_readable_paragraphs_for_faster_whisper_merges_sentences_into_paragraphs() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="итак, друзья, всем привет."),
        TranscriptSegment(start=1.1, end=2.0, text="сегодня разберем тему интеллекта"),
        TranscriptSegment(start=2.1, end=3.0, text="и посмотрим, как это работает."),
        TranscriptSegment(start=6.0, end=7.0, text="во-первых, важен контекст."),
    ]

    paragraphs = build_readable_paragraphs(EngineType.faster_whisper, segments)

    assert len(paragraphs) == 2
    assert paragraphs[0].startswith("Итак")
    assert paragraphs[0].endswith(".")
    assert "Сегодня разберем тему интеллекта" in paragraphs[0]
    assert paragraphs[1].startswith("Во-первых")


def test_build_readable_paragraphs_for_faster_whisper_adds_terminal_punctuation() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=0.6, text="почему люди переоценивают себя"),
        TranscriptSegment(start=0.7, end=1.2, text="и как это связано с опытом"),
        TranscriptSegment(start=2.5, end=3.0, text="это важный вопрос"),
    ]

    paragraphs = build_readable_paragraphs(EngineType.faster_whisper, segments)

    assert len(paragraphs) == 1
    assert "Почему люди переоценивают себя и как это связано с опытом?" in paragraphs[0]
    assert paragraphs[0].endswith("Это важный вопрос.")


def test_build_readable_paragraphs_removes_leading_fillers_softly() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=0.5, text="ну, в общем, это довольно просто"),
        TranscriptSegment(start=0.6, end=1.1, text="и работает стабильно"),
    ]

    paragraphs = build_readable_paragraphs(EngineType.faster_whisper, segments)

    assert paragraphs == ["Это довольно просто и работает стабильно."]


def test_build_readable_paragraphs_uses_punctuator_when_available() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=1.0, text="мы обсудим тему интеллекта итак дальше важен контекст"),
    ]

    paragraphs = build_readable_paragraphs(
        EngineType.faster_whisper,
        segments,
        punctuator=FakePunctuator(),
    )

    assert paragraphs == ["Мы обсудим тему интеллекта. Итак дальше важен контекст."]


def test_readable_processor_falls_back_to_heuristics_when_punctuator_window_fails() -> None:
    processor = ReadableTextProcessor(model_path=None, punctuator=FlakyPunctuator())
    segments = [
        TranscriptSegment(start=0.0, end=0.7, text="почему это важно"),
        TranscriptSegment(start=0.8, end=1.4, text="и как это работает"),
        TranscriptSegment(start=4.0, end=4.5, text="дальше новая тема"),
    ]

    paragraphs = processor.build_paragraphs(EngineType.faster_whisper, segments)

    assert len(paragraphs) >= 1
    assert paragraphs[0].startswith("Почему")


def test_build_readable_paragraphs_falls_back_when_punctuated_output_is_invalid() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=0.7, text="почему это важно"),
        TranscriptSegment(start=0.8, end=1.4, text="и как это работает"),
    ]

    paragraphs = build_readable_paragraphs(
        EngineType.faster_whisper,
        segments,
        punctuator=BrokenPunctuator(),
    )

    assert paragraphs == ["Почему это важно и как это работает?"]


def test_build_readable_paragraphs_cleans_obvious_comma_artifacts() -> None:
    segments = [
        TranscriptSegment(start=0.0, end=0.7, text="итак это важно например человек думает"),
    ]

    paragraphs = build_readable_paragraphs(
        EngineType.faster_whisper,
        segments,
        punctuator=CommaArtifactPunctuator(),
    )

    assert paragraphs == ["Итак, это важно. Например, человек думает?"]
