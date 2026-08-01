"""Stable research-input freshness calculations."""

import json
import re
import unicodedata
from hashlib import sha256
from typing import Literal

_WHITESPACE = re.compile(r"\s+")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return _WHITESPACE.sub(" ", normalized.strip())


def compute_input_hash(
    *,
    topic: str,
    narrations: list[str],
    asset_type: Literal["image", "video"],
    mode: Literal["verified"],
) -> str:
    """Hash normalized research inputs while preserving narration order."""
    payload = {
        "asset_type": asset_type,
        "mode": mode,
        "narrations": [_normalize(narration) for narration in narrations],
        "topic": _normalize(topic),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()
