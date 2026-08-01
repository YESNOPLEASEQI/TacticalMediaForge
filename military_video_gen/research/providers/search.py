"""Search-provider contract."""

from typing import Protocol

from ..models import SearchCandidate


class SearchProvider(Protocol):
    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
    ) -> list[SearchCandidate]: ...
