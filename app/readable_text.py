from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Protocol

from app.types import EngineType, TranscriptSegment


TOPIC_MARKERS = (
    "итак",
    "во-первых",
    "во вторых",
    "во-вторых",
    "во-третьих",
    "теперь",
    "дальше",
    "следующее",
    "например",
    "с другой стороны",
)

QUESTION_MARKERS = (
    "почему",
    "зачем",
    "как",
    "когда",
    "где",
    "кто",
    "что",
    "какой",
    "какая",
    "какие",
    "каким",
    "можно ли",
    "нужно ли",
    "стоит ли",
    "разве",
    "неужели",
    "сколько",
)

LEADING_FILLER_PATTERNS = (
    re.compile(r"^(?:(?:э+|э-э+|эм+|мм+|м-м+)\b)\s*,?\s*", re.IGNORECASE),
    re.compile(r"^(?:(?:ну\s+вот|в общем|короче|собственно|как бы|ну)\b)\s*,?\s*", re.IGNORECASE),
)

TERMINAL_PUNCTUATION_RE = re.compile(r"[.!?…](?:[\"»)]|\])?$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
REPEATED_WORD_RE = re.compile(r"\b([^\W\d_]+)(?:\s+\1\b)+", re.IGNORECASE)
MULTISPACE_RE = re.compile(r"\s{2,}")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)?")
DISCOURSE_MARKER_NORMALIZATIONS = (
    (re.compile(r"\bво\s*,?\s*первых\b", re.IGNORECASE), "во-первых"),
    (re.compile(r"\bво\s*,?\s*вторых\b", re.IGNORECASE), "во-вторых"),
    (re.compile(r"\bво\s*,?\s*третьих\b", re.IGNORECASE), "во-третьих"),
)
DISCOURSE_MARKER_RE = re.compile(r"\b(во-первых|во-вторых|во-третьих|например|итак)\b", re.IGNORECASE)

PUNCTUATION_MAP = {
    "PERIOD": ".",
    "COMMA": ",",
    "QUESTION": "?",
    "TIRE": "—",
    "VOSKL": "!",
    "DVOETOCHIE": ":",
    "PERIODCOMMA": ";",
    "DEFIS": "-",
    "QUESTIONVOSKL": "?!",
    "MNOGOTOCHIE": "…",
    "O": "",
}


class Punctuator(Protocol):
    def punctuate(self, text: str) -> str:
        ...


@dataclass(slots=True)
class TranscriptWindow:
    start: float
    end: float
    gap_before: float
    text: str
    segments: list[TranscriptSegment]


@dataclass(slots=True)
class SentenceChunk:
    start: float
    end: float
    gap_before: float
    text: str


@dataclass(slots=True)
class ParagraphChunk:
    start: float
    end: float
    text: str
    sentences: list[SentenceChunk]


@dataclass(slots=True)
class ReadableDocument:
    paragraphs: list[ParagraphChunk]


@dataclass(slots=True)
class WordTiming:
    text: str
    start: float
    end: float


class RUPunctPunctuator:
    def __init__(self, model_path: Path, device: str = "cpu") -> None:
        self._model_path = Path(model_path)
        self._device = device
        self._pipeline = None

    def punctuate(self, text: str) -> str:
        if not text.strip():
            return ""
        pipe = self._ensure_pipeline()
        items = pipe(text)
        if not items:
            return text

        fragments: list[str] = []
        for item in items:
            word = str(item.get("word") or "").replace("##", "")
            word = word.replace("▁", " ").replace("Ġ", " ").strip()
            if not word or word.startswith("["):
                continue

            label = str(item.get("entity_group") or item.get("entity") or "O").upper()
            casing, punctuation = _parse_rupunct_label(label)
            formatted = _apply_casing(word, casing)
            suffix = PUNCTUATION_MAP.get(punctuation, "")
            fragments.append(f"{formatted}{suffix}")

        punctuated = " ".join(fragment for fragment in fragments if fragment)
        punctuated = _normalize_punctuated_text(punctuated)
        if not _is_usable_punctuated_output(text, punctuated):
            raise ValueError("RUPunct produced invalid output")
        return punctuated or text

    def _ensure_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        if not self._model_path.exists():
            raise FileNotFoundError(f"RUPunct model path does not exist: {self._model_path}")

        from transformers import AutoTokenizer, pipeline

        device_index = -1
        if self._device and self._device.lower() != "cpu":
            device_index = 0

        tokenizer = AutoTokenizer.from_pretrained(
            str(self._model_path),
            strip_accents=False,
            add_prefix_space=True,
        )

        self._pipeline = pipeline(
            "ner",
            model=str(self._model_path),
            tokenizer=tokenizer,
            aggregation_strategy="first",
            device=device_index,
            ignore_labels=[],
        )
        return self._pipeline


class ReadableTextProcessor:
    def __init__(
        self,
        model_path: Path | None,
        punct_device: str = "cpu",
        punctuator: Punctuator | None = None,
    ) -> None:
        self._model_path = Path(model_path) if model_path else None
        self._punct_device = punct_device
        self._punctuator_override = punctuator
        self._punctuator: Punctuator | None = punctuator
        self._punctuator_init_attempted = punctuator is not None

    def build_paragraphs(
        self,
        engine: EngineType,
        segments: Iterable[TranscriptSegment],
    ) -> list[str]:
        punctuator = self._get_punctuator()
        return build_readable_paragraphs(engine, segments, punctuator=punctuator)

    def build_paragraph_chunks(
        self,
        engine: EngineType,
        segments: Iterable[TranscriptSegment],
    ) -> list[ParagraphChunk]:
        punctuator = self._get_punctuator()
        return build_readable_paragraph_chunks(engine, segments, punctuator=punctuator)

    def build_document(
        self,
        engine: EngineType,
        segments: Iterable[TranscriptSegment],
    ) -> ReadableDocument:
        punctuator = self._get_punctuator()
        return build_readable_document(engine, segments, punctuator=punctuator)

    def _get_punctuator(self) -> Punctuator | None:
        if self._punctuator_override is not None:
            return self._punctuator_override
        if self._punctuator_init_attempted:
            return self._punctuator
        self._punctuator_init_attempted = True
        if self._model_path is None or not self._model_path.exists():
            self._punctuator = None
            return None
        try:
            self._punctuator = RUPunctPunctuator(self._model_path, self._punct_device)
        except Exception:
            self._punctuator = None
        return self._punctuator


def build_readable_paragraphs(
    engine: EngineType,
    segments: Iterable[TranscriptSegment],
    punctuator: Punctuator | None = None,
) -> list[str]:
    return [chunk.text for chunk in build_readable_paragraph_chunks(engine, segments, punctuator=punctuator)]


def build_readable_document(
    engine: EngineType,
    segments: Iterable[TranscriptSegment],
    punctuator: Punctuator | None = None,
) -> ReadableDocument:
    return ReadableDocument(
        paragraphs=build_readable_paragraph_chunks(engine, segments, punctuator=punctuator),
    )


def build_readable_paragraph_chunks(
    engine: EngineType,
    segments: Iterable[TranscriptSegment],
    punctuator: Punctuator | None = None,
) -> list[ParagraphChunk]:
    prepared = _prepare_segments(segments)
    if not prepared:
        return []

    if punctuator is None:
        sentences = _build_heuristic_sentences(engine, prepared)
        return _group_paragraph_chunks(sentences)

    windows = _chunk_segments(prepared)
    sentences: list[SentenceChunk] = []
    for window in windows:
        try:
            punctuated = punctuator.punctuate(window.text)
            if not _is_usable_punctuated_output(window.text, punctuated):
                raise ValueError("Invalid punctuated output")
            sentences.extend(_build_sentences_from_punctuated_window(window, punctuated))
        except Exception:
            sentences.extend(_build_heuristic_sentences(engine, window.segments, gap_before=window.gap_before))

    return _group_paragraph_chunks(sentences)


def _prepare_segments(segments: Iterable[TranscriptSegment]) -> list[TranscriptSegment]:
    prepared: list[TranscriptSegment] = []
    for item in segments:
        normalized = _normalize_segment_text(item.text)
        if not normalized:
            continue
        prepared.append(TranscriptSegment(start=item.start, end=item.end, text=normalized))
    return prepared


def _chunk_segments(segments: list[TranscriptSegment]) -> list[TranscriptWindow]:
    windows: list[TranscriptWindow] = []
    buffer: list[TranscriptSegment] = []
    buffer_words = 0
    previous_end: float | None = None
    window_gap_before = 0.0

    for segment in segments:
        gap_before_segment = 0.0 if previous_end is None else max(0.0, segment.start - previous_end)
        previous_end = segment.end
        segment_words = len(segment.text.split())
        force_split = bool(buffer) and (gap_before_segment >= 2.0 or buffer_words >= 180)

        if force_split:
            windows.append(_build_window(buffer, window_gap_before))
            buffer = []
            buffer_words = 0
            window_gap_before = gap_before_segment
        elif not buffer:
            window_gap_before = gap_before_segment

        buffer.append(segment)
        buffer_words += segment_words

        if buffer_words >= 150:
            windows.append(_build_window(buffer, window_gap_before))
            buffer = []
            buffer_words = 0
            window_gap_before = 0.0

    if buffer:
        windows.append(_build_window(buffer, window_gap_before))
    return windows


def _build_window(segments: list[TranscriptSegment], gap_before: float) -> TranscriptWindow:
    return TranscriptWindow(
        start=segments[0].start,
        end=segments[-1].end,
        gap_before=gap_before,
        text=" ".join(segment.text for segment in segments).strip(),
        segments=list(segments),
    )


def _build_sentences_from_punctuated_window(
    window: TranscriptWindow,
    text: str,
) -> list[SentenceChunk]:
    normalized = _normalize_punctuated_text(text)
    if not normalized:
        return []

    sentence_texts = [piece.strip() for piece in SENTENCE_SPLIT_RE.split(normalized) if piece.strip()]
    if not sentence_texts:
        sentence_texts = [normalized]

    sentences: list[SentenceChunk] = []
    word_timeline = _build_word_timeline(window.segments)
    timeline_cursor = 0
    for index, sentence_text in enumerate(sentence_texts):
        cleaned = _finalize_sentence_text(sentence_text)
        if not cleaned:
            continue
        timing, timeline_cursor = _align_sentence_timing(cleaned, word_timeline, timeline_cursor)
        start, end = timing if timing is not None else (window.start, window.end)
        sentences.append(
            SentenceChunk(
                start=start,
                end=end,
                gap_before=window.gap_before if index == 0 else 0.0,
                text=cleaned,
            )
        )
    return sentences


def _build_word_timeline(segments: list[TranscriptSegment]) -> list[WordTiming]:
    timeline: list[WordTiming] = []
    for segment in segments:
        words = WORD_RE.findall(segment.text)
        if not words:
            continue
        duration = max(0.01, segment.end - segment.start)
        for index, word in enumerate(words):
            word_start = segment.start + duration * index / len(words)
            word_end = segment.start + duration * (index + 1) / len(words)
            timeline.append(
                WordTiming(
                    text=_normalize_alignment_word(word),
                    start=word_start,
                    end=max(word_start, word_end),
                )
            )
    return timeline


def _align_sentence_timing(
    sentence_text: str,
    timeline: list[WordTiming],
    cursor: int,
) -> tuple[tuple[float, float] | None, int]:
    sentence_words = [
        _normalize_alignment_word(word)
        for word in WORD_RE.findall(sentence_text)
        if _normalize_alignment_word(word)
    ]
    if not sentence_words or not timeline:
        return None, cursor

    start_index, end_index = _match_sentence_words_to_timeline(sentence_words, timeline, cursor)
    if start_index is None or end_index is None:
        fallback_start = min(max(cursor, 0), len(timeline) - 1)
        fallback_end = min(len(timeline) - 1, fallback_start + max(1, len(sentence_words)) - 1)
        start_index, end_index = fallback_start, fallback_end

    start = timeline[start_index].start
    end = max(start, timeline[end_index].end)
    return (start, end), min(len(timeline), end_index + 1)


def _match_sentence_words_to_timeline(
    sentence_words: list[str],
    timeline: list[WordTiming],
    cursor: int,
) -> tuple[int | None, int | None]:
    if cursor >= len(timeline):
        return None, None

    best: tuple[int, int, int] | None = None
    search_end = min(len(timeline), cursor + max(18, len(sentence_words) * 3))
    for candidate_start in range(cursor, search_end):
        source_index = candidate_start
        first_match: int | None = None
        last_match: int | None = None
        matched = 0
        for word in sentence_words:
            found: int | None = None
            scan_end = min(len(timeline), source_index + 10)
            for scan_index in range(source_index, scan_end):
                if timeline[scan_index].text == word:
                    found = scan_index
                    break
            if found is None:
                continue
            first_match = found if first_match is None else first_match
            last_match = found
            matched += 1
            source_index = found + 1

        if first_match is None or last_match is None:
            continue
        candidate = (matched, first_match, last_match)
        if best is None or candidate[0] > best[0] or (
            candidate[0] == best[0] and candidate[1] < best[1]
        ):
            best = candidate
        if matched == len(sentence_words):
            break

    min_matches = max(1, min(len(sentence_words), max(2, int(len(sentence_words) * 0.45))))
    if best is None or best[0] < min_matches:
        return None, None
    return best[1], best[2]


def _build_heuristic_sentences(
    engine: EngineType,
    segments: list[TranscriptSegment],
    gap_before: float = 0.0,
) -> list[SentenceChunk]:
    if engine == EngineType.faster_whisper:
        return _build_sentences_faster_whisper(segments, initial_gap_before=gap_before)
    return _build_sentences_fallback(segments, initial_gap_before=gap_before)


def _build_sentences_faster_whisper(
    segments: list[TranscriptSegment],
    initial_gap_before: float = 0.0,
) -> list[SentenceChunk]:
    sentences: list[SentenceChunk] = []
    buffer = ""
    buffer_start = 0.0
    buffer_end = 0.0
    previous_end: float | None = None
    sentence_gap_before = initial_gap_before

    for segment in segments:
        pieces = [piece.strip() for piece in SENTENCE_SPLIT_RE.split(segment.text) if piece.strip()]
        if not pieces:
            continue

        gap_before_segment = initial_gap_before if previous_end is None else max(0.0, segment.start - previous_end)
        previous_end = segment.end

        for index, piece in enumerate(pieces):
            gap = gap_before_segment if index == 0 else 0.0
            if buffer and _should_force_sentence_break(buffer, gap, piece):
                sentences.append(_finalize_sentence(buffer_start, buffer_end, sentence_gap_before, buffer))
                buffer = ""
                sentence_gap_before = gap

            if not buffer:
                buffer = piece
                buffer_start = segment.start
                sentence_gap_before = gap
            else:
                buffer = f"{buffer} {piece}".strip()
            buffer_end = segment.end

            if _has_terminal_punctuation(piece):
                sentences.append(_finalize_sentence(buffer_start, buffer_end, sentence_gap_before, buffer))
                buffer = ""
                sentence_gap_before = 0.0

    if buffer:
        sentences.append(_finalize_sentence(buffer_start, buffer_end, sentence_gap_before, buffer))

    return sentences


def _build_sentences_fallback(
    segments: list[TranscriptSegment],
    initial_gap_before: float = 0.0,
) -> list[SentenceChunk]:
    sentences: list[SentenceChunk] = []
    buffer_parts: list[str] = []
    buffer_start = 0.0
    buffer_end = 0.0
    word_count = 0
    previous_end: float | None = None
    sentence_gap_before = initial_gap_before

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue

        gap = initial_gap_before if previous_end is None else max(0.0, segment.start - previous_end)
        previous_end = segment.end

        if buffer_parts and _should_force_sentence_break(" ".join(buffer_parts), gap, text):
            sentences.append(
                _finalize_sentence(buffer_start, buffer_end, sentence_gap_before, " ".join(buffer_parts))
            )
            buffer_parts = []
            word_count = 0
            sentence_gap_before = gap

        if not buffer_parts:
            buffer_start = segment.start
            sentence_gap_before = gap

        buffer_parts.append(text)
        buffer_end = segment.end
        word_count += len(text.split())

        joined = " ".join(buffer_parts)
        if _has_terminal_punctuation(text) or word_count >= 24 or len(joined) >= 180:
            sentences.append(
                _finalize_sentence(buffer_start, buffer_end, sentence_gap_before, joined)
            )
            buffer_parts = []
            word_count = 0
            sentence_gap_before = 0.0

    if buffer_parts:
        sentences.append(
            _finalize_sentence(buffer_start, buffer_end, sentence_gap_before, " ".join(buffer_parts))
        )

    return sentences


def _should_force_sentence_break(current_text: str, gap: float, next_text: str) -> bool:
    if gap >= 1.2:
        return True
    if len(current_text) >= 180:
        return True
    if len(current_text.split()) >= 28:
        return True
    return _starts_new_topic(next_text) and len(current_text.split()) >= 8


def _group_paragraphs(sentences: list[SentenceChunk]) -> list[str]:
    return [chunk.text for chunk in _group_paragraph_chunks(sentences)]


def _group_paragraph_chunks(sentences: list[SentenceChunk]) -> list[ParagraphChunk]:
    chunks: list[ParagraphChunk] = []
    current: list[SentenceChunk] = []

    def flush_current() -> None:
        if not current:
            return
        text = " ".join(sentence.text for sentence in current).strip()
        if text:
            chunks.append(
                ParagraphChunk(
                    start=current[0].start,
                    end=current[-1].end,
                    text=text,
                    sentences=list(current),
                )
            )

    for sentence in sentences:
        if current and (
            sentence.gap_before >= 2.8
            or len(current) >= 5
            or (_starts_new_topic(sentence.text) and len(current) >= 2)
        ):
            flush_current()
            current = []

        current.append(sentence)

    if current:
        flush_current()

    return chunks


def _finalize_sentence(start: float, end: float, gap_before: float, text: str) -> SentenceChunk:
    return SentenceChunk(
        start=start,
        end=end,
        gap_before=gap_before,
        text=_finalize_sentence_text(text),
    )


def _finalize_sentence_text(text: str) -> str:
    cleaned = _clean_sentence_text(text)
    cleaned = _capitalize_sentence(cleaned)
    cleaned = _ensure_sentence_terminal(cleaned)
    return cleaned


def _normalize_segment_text(text: str) -> str:
    normalized = " ".join(text.split())
    normalized = re.sub(r"\s+([,.;:!?…])", r"\1", normalized)
    normalized = re.sub(r"([,.;:!?…])\1+", r"\1", normalized)
    normalized = REPEATED_WORD_RE.sub(r"\1", normalized)
    return normalized.strip()


def _normalize_alignment_word(word: str) -> str:
    return word.strip().lower().replace("ё", "е")


def _normalize_punctuated_text(text: str) -> str:
    normalized = " ".join(text.split())
    normalized = re.sub(r"\s+([,.;:!?…])", r"\1", normalized)
    normalized = re.sub(r"([,.;:!?…])\1+", r"\1", normalized)
    normalized = re.sub(r"\s*—\s*", " — ", normalized)
    normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "-", normalized)
    normalized = re.sub(r"\s+([:;])", r"\1", normalized)
    normalized = _normalize_discourse_markers(normalized)
    normalized = _cleanup_comma_artifacts(normalized)
    normalized = MULTISPACE_RE.sub(" ", normalized)
    return normalized.strip()


def _is_usable_punctuated_output(source_text: str, punctuated_text: str) -> bool:
    source = source_text.strip()
    punctuated = punctuated_text.strip()
    if not source or not punctuated:
        return False

    source_words = WORD_RE.findall(source)
    punctuated_words = WORD_RE.findall(punctuated)
    if source_words and len(punctuated_words) < max(1, int(len(source_words) * 0.6)):
        return False

    source_cyrillic = len(CYRILLIC_RE.findall(source))
    punctuated_cyrillic = len(CYRILLIC_RE.findall(punctuated))
    if source_cyrillic >= 4 and punctuated_cyrillic == 0:
        return False

    if punctuated_words and all(word == "?" for word in punctuated_words):
        return False

    return True


def _clean_sentence_text(text: str) -> str:
    cleaned = " ".join(text.split())
    for pattern in LEADING_FILLER_PATTERNS:
        while True:
            updated = pattern.sub("", cleaned).strip()
            if updated == cleaned:
                break
            cleaned = updated

    cleaned = re.sub(r"\s+([,.;:!?…])", r"\1", cleaned)
    cleaned = re.sub(r"([,.;:!?…])\1+", r"\1", cleaned)
    cleaned = REPEATED_WORD_RE.sub(r"\1", cleaned)
    cleaned = _normalize_discourse_markers(cleaned)
    cleaned = _cleanup_comma_artifacts(cleaned)
    cleaned = MULTISPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" ,")


def _normalize_discourse_markers(text: str) -> str:
    normalized = text
    for pattern, replacement in DISCOURSE_MARKER_NORMALIZATIONS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _cleanup_comma_artifacts(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r",\s*,+", ", ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*([.?!…;:])", r"\1", cleaned)
    cleaned = re.sub(r"([.?!…])\s*,", r"\1", cleaned)
    cleaned = re.sub(r"\(\s*,\s*", "(", cleaned)
    cleaned = re.sub(r"\[\s*,\s*", "[", cleaned)
    cleaned = DISCOURSE_MARKER_RE.sub(lambda match: match.group(1), cleaned)
    cleaned = re.sub(
        r"\b(во-первых|во-вторых|во-третьих|например|итак)\s*,\s*,+",
        r"\1, ",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _capitalize_sentence(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return f"{text[:index]}{char.upper()}{text[index + 1:]}"
    return text


def _ensure_sentence_terminal(text: str) -> str:
    if not text:
        return text
    if _has_terminal_punctuation(text):
        return text
    return f"{text}{'?' if _looks_like_question(text) else '.'}"


def _looks_like_question(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(marker) for marker in QUESTION_MARKERS)


def _has_terminal_punctuation(text: str) -> bool:
    return bool(TERMINAL_PUNCTUATION_RE.search(text.strip()))


def _starts_new_topic(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(marker) for marker in TOPIC_MARKERS)


def _parse_rupunct_label(label: str) -> tuple[str, str]:
    for prefix in ("UPPER_TOTAL_", "UPPER_", "LOWER_"):
        if label.startswith(prefix):
            return prefix.removesuffix("_"), label[len(prefix):]
    return "LOWER", label


def _apply_casing(word: str, casing: str) -> str:
    if casing == "UPPER_TOTAL":
        return word.upper()
    if casing == "UPPER":
        for index, char in enumerate(word):
            if char.isalpha():
                return f"{word[:index]}{char.upper()}{word[index + 1:]}"
        return word
    return word.lower()
