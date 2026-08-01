"""Bounded file cache for fetched research pages and failures."""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from .crawlers.security import normalize_public_url


class ResearchCache:
    def __init__(
        self,
        root: Path,
        *,
        cache_ttl_hours: int = 24,
        official_cache_ttl_hours: int = 168,
        failed_cache_ttl_minutes: int = 15,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.official_ttl = timedelta(hours=official_cache_ttl_hours)
        self.failed_ttl = timedelta(minutes=failed_cache_ttl_minutes)
        self.clock = clock or (lambda: datetime.now(UTC))

    def _path(self, url: str, config_version: str, kind: str) -> Path:
        normalized = normalize_public_url(url)
        key = sha256(f"{normalized}\n{config_version}\n{kind}".encode()).hexdigest()
        return self.root / f"{key}.json"

    def put(
        self,
        url: str,
        config_version: str,
        value: dict,
        *,
        official: bool = False,
    ) -> None:
        payload = {
            "created_at": self.clock().isoformat(),
            "official": official,
            "value": value,
        }
        self._path(url, config_version, "success").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def get(
        self,
        url: str,
        config_version: str,
        *,
        force_refresh: bool = False,
    ) -> dict | None:
        if force_refresh:
            return None
        path = self._path(url, config_version, "success")
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(payload["created_at"])
            value = payload["value"]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None
        ttl = self.official_ttl if payload.get("official") else self.cache_ttl
        if self.clock() - created > ttl:
            return None
        return value

    def put_failure(self, url: str, config_version: str, error: str) -> None:
        self._path(url, config_version, "failure").write_text(
            json.dumps({"created_at": self.clock().isoformat(), "error": error}),
            encoding="utf-8",
        )

    def get_failure(self, url: str, config_version: str) -> str | None:
        path = self._path(url, config_version, "failure")
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(payload["created_at"])
            error = payload["error"]
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            return None
        if self.clock() - created > self.failed_ttl:
            return None
        return error
