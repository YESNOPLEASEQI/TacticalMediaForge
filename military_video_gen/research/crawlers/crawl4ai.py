"""Restricted Crawl4AI Docker API client."""

import asyncio
import json
import os
import socket
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urljoin, urlsplit

import httpx

from military_video_gen.config.schema import ResearchCrawlConfig

from ..models import CrawledDocument, SearchCandidate
from .security import URLSafetyChecker


class CrawlResponseTooLarge(RuntimeError):
    """The Crawl4AI proxy response exceeded the configured byte budget."""


class Crawl4AIProvider:
    def __init__(
        self,
        config: ResearchCrawlConfig,
        *,
        client: httpx.AsyncClient | None = None,
        safety_checker: URLSafetyChecker | None = None,
    ) -> None:
        self.config = config
        self.client = client
        self.safety_checker = safety_checker or URLSafetyChecker(
            allow_proxy_fake_ip=config.allow_proxy_fake_ip,
        )

    async def crawl_many(
        self,
        candidates: list[SearchCandidate],
        *,
        force_refresh: bool,
    ) -> list[CrawledDocument]:
        global_semaphore = asyncio.Semaphore(self.config.global_concurrency)
        domain_semaphores: dict[str, asyncio.Semaphore] = {}

        async def crawl_candidate(candidate: SearchCandidate) -> list[CrawledDocument]:
            domain = urlsplit(str(candidate.url)).hostname or ""
            domain_semaphore = domain_semaphores.setdefault(
                domain,
                asyncio.Semaphore(self.config.per_domain_concurrency),
            )
            async with domain_semaphore, global_semaphore:
                last_error = "crawl_failed"
                for attempt in range(3):
                    try:
                        documents = await self._crawl_one(
                            candidate,
                            force_refresh=force_refresh,
                        )
                        if any(
                            not document.error and document.markdown.strip()
                            for document in documents
                        ):
                            return documents
                        if documents and documents[0].error:
                            last_error = documents[0].error
                    except httpx.TimeoutException:
                        last_error = "crawl_timeout"
                    except httpx.HTTPStatusError as error:
                        status = error.response.status_code
                        last_error = f"crawl_http_{status}"
                        if status < 500 and status != 429:
                            break
                    except httpx.HTTPError:
                        last_error = "crawl_http_error"
                    except socket.gaierror:
                        last_error = "dns_resolution_failed"
                    if attempt < 2:
                        await asyncio.sleep(0.75 * (2**attempt))
                return [self._failed_document(candidate, error=last_error)]

        batches = await asyncio.gather(
            *(crawl_candidate(candidate) for candidate in candidates)
        )
        return [document for batch in batches for document in batch]

    @staticmethod
    def _failed_document(
        candidate: SearchCandidate,
        *,
        error: str,
    ) -> CrawledDocument:
        return CrawledDocument(
            url=candidate.url,
            title=candidate.title,
            markdown="",
            content_hash=sha256(b"").hexdigest(),
            fetched_at=datetime.now(UTC),
            error=error,
        )

    @staticmethod
    def _normalize_links(value: object, *, base_url: str) -> list[str]:
        entries: list[object] = []
        if isinstance(value, list):
            entries = value
        elif isinstance(value, dict):
            for group in value.values():
                if isinstance(group, list):
                    entries.extend(group)

        links: list[str] = []
        seen: set[str] = set()
        for entry in entries:
            href = entry.get("href") if isinstance(entry, dict) else entry
            if not isinstance(href, str) or not href.strip():
                continue
            absolute = urljoin(base_url, href.strip())
            if urlsplit(absolute).scheme not in {"http", "https"} or absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links

    async def _crawl_one(
        self,
        candidate: SearchCandidate,
        *,
        force_refresh: bool,
    ) -> list[CrawledDocument]:
        url = await self.safety_checker.validate(str(candidate.url))
        token = os.environ.get(self.config.auth_token_env, "")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        payload = {
            "urls": [url],
            "browser_config": {"headless": True},
            "crawler_config": {
                "check_robots_txt": self.config.respect_robots_txt,
                "page_timeout": int(self.config.page_timeout_seconds * 1000),
                # Redirects happen inside the crawler's own network namespace,
                # where this process cannot validate every hop before access.
                # Fail closed here; callers may submit a revalidated final URL
                # as a new candidate instead of permitting blind redirects.
                "max_redirects": 0,
                "cache_mode": "BYPASS" if force_refresh else "ENABLED",
            },
        }
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient()
        try:
            timeout = httpx.Timeout(
                self.config.request_timeout_seconds,
                connect=self.config.connect_timeout_seconds,
            )
            request = client.build_request(
                "POST",
                f"{self.config.base_url.rstrip('/')}/crawl",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response = await client.send(request, stream=True)
            try:
                response.raise_for_status()
                raw = bytearray()
                limit = max(self.config.max_html_bytes, self.config.max_pdf_bytes)
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > limit:
                        raise CrawlResponseTooLarge(
                            "Crawl4AI response exceeded size limit"
                        )
            finally:
                await response.aclose()
        finally:
            if owns_client:
                await client.aclose()
        data = json.loads(raw)
        results = data.get("results", data if isinstance(data, list) else [])
        documents: list[CrawledDocument] = []
        for item in results:
            final_url = await self.safety_checker.validate(item.get("url") or url)
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            response_headers = item.get("response_headers")
            if not isinstance(response_headers, dict):
                response_headers = {}
            markdown = item.get("markdown") or ""
            if isinstance(markdown, dict):
                markdown = markdown.get("fit_markdown") or markdown.get("raw_markdown") or ""
            markdown = markdown[:100_000]
            content_type = (
                item.get("content_type")
                or response_headers.get("content-type")
                or response_headers.get("Content-Type")
                or "text/html"
            )
            error = item.get("error_message") if item.get("success") is False else None
            if content_type.startswith("application/pdf") and not markdown.strip():
                error = "pdf_without_text_layer"
            documents.append(
                CrawledDocument(
                    url=final_url,
                    canonical_url=item.get("canonical_url")
                    or metadata.get("canonical_url"),
                    title=item.get("title") or metadata.get("title") or candidate.title,
                    markdown=markdown,
                    links=self._normalize_links(
                        item.get("links"),
                        base_url=final_url,
                    ),
                    published_at=item.get("published_at") or metadata.get("published_at"),
                    content_type=content_type,
                    content_hash=item.get("content_hash")
                    or sha256(markdown.encode("utf-8")).hexdigest(),
                    fetched_at=datetime.now(UTC),
                    truncated=len(markdown) >= 100_000,
                    error=error,
                )
            )
        return documents
