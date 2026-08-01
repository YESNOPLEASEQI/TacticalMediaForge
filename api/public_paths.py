"""Safe conversion of internal filesystem paths for public API responses."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from fastapi import Request

from military_video_gen.utils.os_util import get_root_path
from military_video_gen.utils.safety import redact_url_for_log, sanitize_error_message

_PUBLIC_PREFIXES = (
    "output",
    "workflows",
    "templates",
    "bgm",
    "data/bgm",
    "data/templates",
    "resources",
)
_PATH_KEYS = {"path", "local_path", "ref_audio", "image", "attachment", "attachments", "assets"}


def to_public_file_path(file_path: str | Path) -> str:
    """Return an allowlisted project-relative path without revealing its root."""
    raw = str(file_path).strip()
    if not raw or "\x00" in raw:
        raise ValueError("public file path is invalid")
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https", "data", "file"}:
        raise ValueError("public file path must be local")

    project_root = Path(get_root_path()).resolve()
    normalized = raw.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or path.drive:
        candidate = path.resolve()
    else:
        first = normalized.lstrip("./")
        has_public_prefix = any(
            first == prefix or first.startswith(f"{prefix}/")
            for prefix in _PUBLIC_PREFIXES
        )
        candidate = (project_root / (first if has_public_prefix else f"output/{first}")).resolve()

    allowed_roots = [(project_root / prefix).resolve() for prefix in _PUBLIC_PREFIXES]
    if not any(candidate == root or candidate.is_relative_to(root) for root in allowed_roots):
        raise ValueError("file is outside public project roots")
    return candidate.relative_to(project_root).as_posix()


def to_public_file_url(request: Request, file_path: str | Path) -> str:
    """Build an API file URL from an internal or project-relative path."""
    public_path = to_public_file_path(file_path)
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/files/{quote(public_path, safe='/')}"


def public_api_file_reference(value: object) -> str | None:
    """Normalize an existing API file URL to a safe origin-relative reference."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    path = parsed.path if parsed.scheme in {"http", "https"} else value.split("?", 1)[0]
    prefix = "/api/files/"
    if not path.startswith(prefix):
        return None
    try:
        public_path = to_public_file_path(unquote(path[len(prefix) :]))
    except ValueError:
        return None
    return f"{prefix}{quote(public_path, safe='/')}"


def sanitize_public_payload(value: Any, *, field_name: str | None = None) -> Any:
    """Recursively redact private paths and signed URL credentials."""
    if isinstance(value, dict):
        return {
            str(key): sanitize_public_payload(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_public_payload(item, field_name=field_name) for item in value]
    if isinstance(value, Path):
        value = str(value)
    if not isinstance(value, str):
        return value

    public_reference = public_api_file_reference(value)
    if public_reference is not None:
        return public_reference

    path_field = bool(
        field_name
        and (
            field_name in _PATH_KEYS
            or field_name.endswith("_path")
            or field_name.endswith("_paths")
        )
    )
    if path_field:
        try:
            return to_public_file_path(value)
        except ValueError:
            return None

    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https", "data", "file"}:
        return redact_url_for_log(value)
    candidate = Path(value.replace("\\", "/"))
    if candidate.is_absolute() or candidate.drive:
        try:
            return to_public_file_path(value)
        except ValueError:
            return "<private-path>"
    return sanitize_error_message(value)
