"""Split one narration into short, proportionally timed subtitle cues."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_CLAUSE_RE = re.compile(r"[^，,。！？!?；;：:\n]+[，,。！？!?；;：:]?")


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start: float
    end: float


def split_subtitle_text(
    text: str,
    *,
    max_han_chars: int = 16,
    max_latin_chars: int = 42,
) -> list[str]:
    """Return compact subtitle cards while preserving the narration text."""
    normalized = re.sub(r"[ \t\r\f\v]+", " ", text).strip()
    if not normalized:
        return []

    limit = max_han_chars if _HAN_RE.search(normalized) else max_latin_chars
    clauses = [match.group(0).strip() for match in _CLAUSE_RE.finditer(normalized)]
    if not clauses:
        clauses = [normalized]

    chunks: list[str] = []
    current = ""
    for clause in clauses:
        candidate = f"{current}{clause}"
        if current and _display_length(candidate) > limit:
            chunks.extend(_split_long_chunk(current, limit))
            current = clause
        else:
            current = candidate
    if current:
        chunks.extend(_split_long_chunk(current, limit))
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def build_subtitle_cues(text: str, duration: float) -> list[SubtitleCue]:
    """Allocate the scene's audio duration across its subtitle cards."""
    chunks = split_subtitle_text(text)
    if not chunks:
        return []

    safe_duration = max(float(duration), 0.001)
    weights = [_speech_weight(chunk) for chunk in chunks]
    total_weight = sum(weights)
    cues: list[SubtitleCue] = []
    elapsed_weight = 0.0
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        start = safe_duration * elapsed_weight / total_weight
        elapsed_weight += weight
        end = (
            safe_duration
            if index == len(chunks) - 1
            else safe_duration * elapsed_weight / total_weight
        )
        cues.append(SubtitleCue(text=chunk, start=start, end=end))
    return cues


def _split_long_chunk(text: str, limit: int) -> list[str]:
    if _display_length(text) <= limit:
        return [text]
    if _HAN_RE.search(text):
        return [text[index:index + limit] for index in range(0, len(text), limit)]

    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if current and len(candidate) > limit:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _display_length(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _speech_weight(text: str) -> int:
    han_count = len(_HAN_RE.findall(text))
    latin_words = len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", text))
    return max(1, han_count + latin_words * 2)
