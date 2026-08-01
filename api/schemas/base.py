"""
Base schemas
"""

from pathlib import PurePosixPath
from typing import Any, Optional

from pydantic import BaseModel

_REFERENCE_AUDIO_SUFFIXES = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav"}


def validate_reference_audio_path(value: Optional[str]) -> Optional[str]:
    """Allow voice-cloning inputs only from explicit project media roots."""
    if not value:
        return value
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = tuple(part.casefold() for part in path.parts)
    allowed_root = (
        bool(parts)
        and (
            parts[0] in {"temp", "output"}
            or (len(parts) >= 2 and parts[:2] == ("data", "audio"))
        )
    )
    if (
        path.is_absolute()
        or ".." in path.parts
        or "\x00" in value
        or ":" in normalized
        or not allowed_root
        or path.suffix.casefold() not in _REFERENCE_AUDIO_SUFFIXES
    ):
        raise ValueError(
            "ref_audio must be an audio file under temp/, output/, or data/audio/"
        )
    return value


class BaseResponse(BaseModel):
    """Base API response"""
    success: bool = True
    message: str = "Success"
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response"""
    success: bool = False
    message: str
    error: Optional[str] = None

