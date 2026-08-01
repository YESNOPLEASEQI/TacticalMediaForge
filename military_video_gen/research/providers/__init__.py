"""Research search providers."""

from .search import SearchProvider
from .searxng import SearXNGProvider

__all__ = ["SearXNGProvider", "SearchProvider"]
