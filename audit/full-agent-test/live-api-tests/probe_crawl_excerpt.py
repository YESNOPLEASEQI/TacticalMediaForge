"""Inspect the exact safe excerpts sent to evidence extraction."""

import asyncio
import json

from military_video_gen.config import config_manager
from military_video_gen.research.crawlers.crawl4ai import Crawl4AIProvider
from military_video_gen.research.evidence_extractor import EvidenceExtractor
from military_video_gen.research.models import SearchCandidate, Source, SourceType
from military_video_gen.services.llm_service import LLMService


URLS = [
    "https://www.lockheedmartin.com/en-us/news/features/history/f16.html",
    "https://news.lockheedmartin.com/2003-08-18-Lockheed-Martin-Commemorates-25th-Anniversary-of-First-Global-Production-F-16-Delivery",
]


async def main() -> None:
    provider = Crawl4AIProvider(config_manager.config.research.crawl)
    candidates = [SearchCandidate(url=url, title="F-16 official history") for url in URLS]
    documents = await provider.crawl_many(candidates, force_refresh=False)
    result = []
    for document in documents:
        excerpt = EvidenceExtractor._build_safe_excerpt(
            document.markdown,
            title=document.title,
        )
        result.append({
            "url": str(document.url),
            "error": document.error,
            "content_hash": document.content_hash,
            "markdown_length": len(document.markdown),
            "excerpt": excerpt,
        })
    extractor = EvidenceExtractor(
        LLMService({}),
        model=config_manager.config.research.verification.structured_model,
    )
    sources = [
        Source(
            id=f"source-{index}",
            url=document.url,
            canonical_url=document.canonical_url,
            title=document.title,
            source_type=SourceType.MANUFACTURER,
            fetched_at=document.fetched_at,
            content_hash=document.content_hash,
            score=0.8,
        )
        for index, document in enumerate(documents, start=1)
    ]
    claims = await extractor.extract(documents, sources)
    result.append({
        "live_extracted_claims": [claim.model_dump(mode="json") for claim in claims]
    })
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
