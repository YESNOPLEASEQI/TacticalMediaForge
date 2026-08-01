"""Minimal SearXNG JSON Search API client."""

import re

import httpx
from pydantic import ValidationError

from ..models import SearchCandidate


class SearchUnavailableError(RuntimeError):
    """The configured search service could not answer a query."""


class SearXNGProvider:
    _MIN_RESULTS_BEFORE_FALLBACK = 3

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 20,
        engines: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.engines = [engine.strip() for engine in (engines or []) if engine.strip()]
        self.client = client

    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
    ) -> list[SearchCandidate]:
        if language is None and not re.search(r"[\u3400-\u9fff]", query):
            language = "en"
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            payload = await self._request_payload(
                client,
                query=query,
                language=language,
                engines=self.engines,
            )

            # Explicit engine selection can partially succeed while one engine
            # is blocked by a CAPTCHA or timeout.  A non-empty but tiny result
            # set must not suppress the healthy engines enabled by SearXNG.
            if self.engines and self._needs_enabled_engine_fallback(payload):
                fallback_payload = await self._request_payload(
                    client,
                    query=query,
                    language=language,
                    engines=[],
                )
                payload = self._merge_payload_results(payload, fallback_payload)
        finally:
            if owns_client:
                await client.aclose()

        candidates: list[SearchCandidate] = []
        for result in payload.get("results", []):
            try:
                candidates.append(
                    SearchCandidate(
                        url=result["url"],
                        title=result.get("title") or result["url"],
                        snippet=result.get("content") or "",
                        query=query,
                    )
                )
            except (KeyError, TypeError, ValidationError):
                continue
        return candidates

    @classmethod
    def _needs_enabled_engine_fallback(cls, payload: dict) -> bool:
        results = payload.get("results")
        unique_urls = (
            {
                result.get("url")
                for result in results
                if isinstance(result, dict) and isinstance(result.get("url"), str)
            }
            if isinstance(results, list)
            else set()
        )
        return bool(payload.get("unresponsive_engines")) or (
            len(unique_urls) < cls._MIN_RESULTS_BEFORE_FALLBACK
        )

    @staticmethod
    def _merge_payload_results(primary: dict, fallback: dict) -> dict:
        merged = dict(primary)
        results: list[object] = []
        seen_urls: set[str] = set()
        for payload in (primary, fallback):
            entries = payload.get("results")
            if not isinstance(entries, list):
                continue
            for result in entries:
                if not isinstance(result, dict):
                    results.append(result)
                    continue
                url = result.get("url")
                if isinstance(url, str):
                    normalized_url = url.rstrip("/")
                    if normalized_url in seen_urls:
                        continue
                    seen_urls.add(normalized_url)
                results.append(result)
        merged["results"] = results
        return merged

    async def _request_payload(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        language: str | None,
        engines: list[str],
    ) -> dict:
        params = {"q": query, "format": "json"}
        if engines:
            params["engines"] = ",".join(engines)
        if language:
            params["language"] = language
        try:
            response = await client.get(
                f"{self.base_url}/search",
                params=params,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("SearXNG response is not a JSON object")
            return payload
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise SearchUnavailableError("SearXNG search service is unavailable") from error
