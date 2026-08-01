"""Pure media contract validation plus a small ffprobe adapter."""

from __future__ import annotations

import math
import re
import unicodedata
from pathlib import Path
from typing import Any

from military_video_gen.utils.safety import redact_path_for_log

_MEDIA_TYPES = {
    "image": ("image/", "application/octet-stream"),
    "video": ("video/", "application/octet-stream"),
    "audio": ("audio/", "application/octet-stream"),
}


def validate_media_probe(
    probe: dict[str, Any] | None,
    *,
    require_audio: bool = False,
) -> float:
    """Validate ffprobe output and return its finite positive duration."""
    if probe is None:
        raise ValueError("media probe is missing")
    streams = probe.get("streams")
    if not isinstance(streams, list) or not streams:
        raise ValueError("media probe has no streams")
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise ValueError("media probe has no video stream")
    if require_audio and not any(
        stream.get("codec_type") == "audio" for stream in streams
    ):
        raise ValueError("media probe has no audio stream")
    try:
        duration = float((probe.get("format") or {}).get("duration"))
    except (TypeError, ValueError) as exc:
        raise ValueError("media duration is missing or invalid") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("media duration must be finite and positive")
    return duration


def probe_media_file(path: str | Path, *, require_audio: bool = False) -> float:
    """Probe a non-empty local media file and enforce the final-media contract."""
    media_path = Path(path)
    if not media_path.is_file():
        raise ValueError(f"media file is missing: {redact_path_for_log(media_path)}")
    if media_path.stat().st_size <= 0:
        raise ValueError(f"media file is empty: {redact_path_for_log(media_path)}")
    import ffmpeg

    try:
        probe = ffmpeg.probe(str(media_path))
    except Exception as exc:
        raise ValueError(
            f"media file cannot be decoded: {redact_path_for_log(media_path)}"
        ) from exc
    return validate_media_probe(probe, require_audio=require_audio)


def validate_audio_probe(probe: dict[str, Any] | None) -> float:
    """Validate ffprobe output for a decodable finite-duration audio artifact."""
    if probe is None:
        raise ValueError("audio probe is missing")
    streams = probe.get("streams")
    if not isinstance(streams, list) or not any(
        stream.get("codec_type") == "audio" for stream in streams
    ):
        raise ValueError("audio probe has no audio stream")
    try:
        duration = float((probe.get("format") or {}).get("duration"))
    except (TypeError, ValueError) as exc:
        raise ValueError("audio duration is missing or invalid") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("audio duration must be finite and positive")
    return duration


def probe_audio_file(path: str | Path) -> float:
    """Probe a non-empty local audio file without duration estimation fallback."""
    audio_path = Path(path)
    if not audio_path.is_file() or audio_path.stat().st_size <= 0:
        raise ValueError("audio file is missing or empty")
    import ffmpeg

    try:
        probe = ffmpeg.probe(str(audio_path))
    except Exception as exc:
        raise ValueError(
            f"audio file cannot be decoded: {redact_path_for_log(audio_path)}"
        ) from exc
    return validate_audio_probe(probe)


def validate_local_media_file(path: str | Path, *, media_kind: str) -> None:
    """Decode-check a downloaded image or probe a downloaded video."""
    media_path = Path(path)
    if not media_path.is_file() or media_path.stat().st_size <= 0:
        raise ValueError(f"downloaded {media_kind} is missing or empty")
    if media_kind == "video":
        probe_media_file(media_path)
        return
    if media_kind != "image":
        raise ValueError(f"unsupported media kind: {media_kind}")
    try:
        from PIL import Image

        with Image.open(media_path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(
            "downloaded image cannot be decoded: "
            f"{redact_path_for_log(media_path)}"
        ) from exc


def validate_project_media_path(path: str | Path) -> Path:
    """Resolve a provider-returned path inside approved project media roots."""
    from military_video_gen.utils.os_util import get_root_path

    candidate = Path(path).resolve()
    roots = [
        Path(get_root_path(name)).resolve()
        for name in ("output", "temp", "data")
    ]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise ValueError("local media path is outside approved project roots")
    return candidate


def validate_generated_output(
    path: str | Path,
    *,
    media_kind: str,
) -> tuple[Path, float | None]:
    """Validate a provider artifact and remove it when it is corrupt."""
    candidate = validate_project_media_path(path)
    try:
        if media_kind == "audio":
            return candidate, probe_audio_file(candidate)
        validate_local_media_file(candidate, media_kind=media_kind)
        return candidate, None
    except Exception:
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
        raise


def validate_download_payload(
    content: bytes,
    content_type: str | None,
    *,
    media_kind: str,
    max_bytes: int = 100 * 1024 * 1024,
) -> None:
    """Reject empty, oversized, or obviously mislabelled download bodies."""
    if not content:
        raise ValueError("downloaded media is empty")
    if len(content) > max_bytes:
        raise ValueError("downloaded media exceeds the size limit")
    allowed = _MEDIA_TYPES.get(media_kind)
    if allowed is None:
        raise ValueError(f"unsupported media kind: {media_kind}")
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    if not normalized or not normalized.startswith(allowed):
        raise ValueError(f"unexpected media content type: {normalized or 'missing'}")


def safe_output_filename(
    value: str | None,
    *,
    suffix: str,
    fallback: str,
    max_stem_length: int = 96,
) -> str:
    """Convert a user title to one portable filename component."""
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ._")
    if normalized in {"", ".", ".."}:
        normalized = fallback
    stem = normalized[:max_stem_length].rstrip(" ._") or fallback
    clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{stem}{clean_suffix}"
