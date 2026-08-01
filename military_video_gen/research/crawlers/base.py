"""Crawler-provider contract."""

from typing import Protocol

from ..models import CrawledDocument, SearchCandidate


class CrawlProvider(Protocol):
    async def crawl_many(
        self,
        candidates: list[SearchCandidate],
        *,
        force_refresh: bool,
    ) -> list[CrawledDocument]: ...
