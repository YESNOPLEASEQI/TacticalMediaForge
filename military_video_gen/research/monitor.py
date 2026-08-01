"""Persistent, redacted diagnostics for the research workflow."""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from military_video_gen.config.schema import ResearchConfig


class ResearchMonitor:
    """Store and expose a bounded history of research events."""

    def __init__(
        self,
        path: str | Path = "data/logs/research-monitor.jsonl",
        *,
        max_bytes: int = 5_242_880,
        backup_count: int = 3,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()

    @staticmethod
    def _redact(message: str | None) -> str | None:
        if message is None:
            return None
        redacted = re.sub(
            r"(?i)\bBearer\s+[^\s,;]+",
            "Bearer [REDACTED]",
            message,
        )
        redacted = re.sub(
            r"(?i)\b(token|api[_-]?key|authorization)\s*[:=]\s*[^\s&]+",
            lambda match: f"{match.group(1)}=[REDACTED]",
            redacted,
        )

        def sanitize_url(match: re.Match[str]) -> str:
            parsed = urlsplit(match.group(0))
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return urlunsplit((parsed.scheme, host, parsed.path, "", ""))

        redacted = re.sub(r"https?://[^\s]+", sanitize_url, redacted)
        return redacted[:500]

    def _backup_path(self, index: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{index}")

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.exists() or self.path.stat().st_size + incoming_bytes <= self.max_bytes:
            return
        if self.backup_count <= 0:
            self.path.unlink()
            return
        oldest = self._backup_path(self.backup_count)
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backup_count - 1, 0, -1):
            source = self._backup_path(index)
            if source.exists():
                source.replace(self._backup_path(index + 1))
        self.path.replace(self._backup_path(1))

    def record(
        self,
        *,
        event: str,
        status: str,
        job_id: str | None = None,
        project_id: str | None = None,
        phase: str | None = None,
        message: str | None = None,
        metrics: dict[str, str | int | float | bool] | None = None,
    ) -> None:
        item = {
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "event": event,
            "status": status,
            "job_id": job_id,
            "project_id": project_id,
            "phase": phase,
            "message": self._redact(message),
            "metrics": {
                key: self._redact(value) if isinstance(value, str) else value
                for key, value in (metrics or {}).items()
            },
        }
        line = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded_size = len(line.encode("utf-8"))
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed(encoded_size)
            with self.path.open("a", encoding="utf-8", newline="") as output:
                output.write(line)

    def read_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        with self._lock:
            paths = [
                self._backup_path(index)
                for index in range(self.backup_count, 0, -1)
                if self._backup_path(index).exists()
            ]
            if self.path.exists():
                paths.append(self.path)
            events: list[dict[str, Any]] = []
            for path in paths:
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict):
                        events.append(value)
            return list(reversed(events[-limit:]))


research_monitor = ResearchMonitor()


async def collect_research_diagnostics(
    config: ResearchConfig,
    *,
    monitor: ResearchMonitor | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Return capability state without burdening the lightweight health route."""
    monitor = monitor or research_monitor
    token = os.getenv(config.crawl.auth_token_env, "")
    if not config.enabled:
        not_checked = {"status": "not_checked", "latency_ms": None, "error": None}
        return {
            "status": "disabled",
            "enabled": False,
            "default_mode": config.default_mode,
            "token_configured": bool(token),
            "services": {
                "searxng": dict(not_checked),
                "crawl4ai": dict(not_checked),
            },
            "recent_events": monitor.read_recent(),
        }

    async def probe(
        service_client: httpx.AsyncClient,
        base_url: str,
        path: str,
        *,
        bearer_token: str = "",
    ) -> dict[str, Any]:
        started = perf_counter()
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else None
        try:
            response = await service_client.get(
                f"{base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=headers,
            )
            response.raise_for_status()
            return {
                "status": "reachable",
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": None,
            }
        except (httpx.HTTPError, ValueError, TypeError) as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            message = type(error).__name__
            if status_code is not None:
                message = f"{message}: HTTP {status_code}"
            return {
                "status": "unreachable",
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": ResearchMonitor._redact(message),
            }

    async def probe_search(service_client: httpx.AsyncClient) -> dict[str, Any]:
        started = perf_counter()
        try:
            response = await service_client.get(
                f"{config.search.base_url.rstrip('/')}/search",
                params={
                    "q": "公开资料",
                    "format": "json",
                    "language": "zh-CN",
                    "engines": ",".join(config.search.engines),
                },
                timeout=min(10.0, config.search.timeout_seconds),
            )
            response.raise_for_status()
            payload = response.json()
            result_count = len(payload.get("results") or [])
            if result_count == 0:
                return {
                    "status": "unreachable",
                    "latency_ms": round((perf_counter() - started) * 1000),
                    "error": "search_empty",
                }
            return {
                "status": "reachable",
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": None,
            }
        except (httpx.HTTPError, ValueError, TypeError) as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            message = type(error).__name__
            if status_code is not None:
                message = f"{message}: HTTP {status_code}"
            return {
                "status": "unreachable",
                "latency_ms": round((perf_counter() - started) * 1000),
                "error": ResearchMonitor._redact(message),
            }

    owns_client = client is None
    service_client = client or httpx.AsyncClient(timeout=3.0, follow_redirects=False)
    try:
        searxng = await probe_search(service_client)
        crawl4ai = await probe(
            service_client,
            config.crawl.base_url,
            "/health",
            bearer_token=token,
        )
    finally:
        if owns_client:
            await service_client.aclose()

    services = {"searxng": searxng, "crawl4ai": crawl4ai}
    ready = all(item["status"] == "reachable" for item in services.values())
    return {
        "status": "ready" if ready else "degraded",
        "enabled": True,
        "default_mode": config.default_mode,
        "token_configured": bool(token),
        "services": services,
        "recent_events": monitor.read_recent(),
    }
