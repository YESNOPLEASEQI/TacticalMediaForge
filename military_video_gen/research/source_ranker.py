"""Source scoring and independent-copy grouping."""

from collections import defaultdict

from .crawlers.security import normalize_public_url
from .models import CrawledDocument, Source, SourceType

_IDENTITY_SCORE = {
    SourceType.OFFICIAL: 1.0,
    SourceType.GOVERNMENT: 0.95,
    SourceType.RESEARCH: 0.85,
    SourceType.MANUFACTURER: 0.8,
    SourceType.NEWS: 0.65,
    SourceType.REFERENCE: 0.6,
    SourceType.OTHER: 0.45,
}


def score_claim_source(source: Source, *, claim_kind: str) -> float:
    identity = _IDENTITY_SCORE[source.source_type]
    relevance = 0.9
    independence = 0.8 if source.independence_group else 0.65
    timeliness = 0.8 if source.published_at else 0.6
    score = identity * 0.35 + relevance * 0.3 + independence * 0.2 + timeliness * 0.15
    if (
        source.source_type is SourceType.MANUFACTURER
        and claim_kind == "operational_effectiveness"
    ):
        score *= 0.65
    # Unknown publishers are discovery inputs, not verification authorities.
    # Fixed relevance and freshness bonuses must never lift them above the
    # low-confidence verification threshold on their own.
    if source.source_type is SourceType.OTHER:
        score = min(score, 0.59)
    return max(0, min(1, score))


def deduplicate_documents(
    documents: list[CrawledDocument],
) -> tuple[list[CrawledDocument], dict[str, str]]:
    by_hash: dict[str, list[CrawledDocument]] = defaultdict(list)
    for document in documents:
        by_hash[document.content_hash].append(document)

    kept: list[CrawledDocument] = []
    groups: dict[str, str] = {}
    for content_hash, copies in by_hash.items():
        canonical = min(
            normalize_public_url(str(document.canonical_url or document.url))
            for document in copies
        )
        kept.append(copies[0])
        group = f"content:{content_hash}"
        for document in copies:
            groups[normalize_public_url(str(document.url))] = group
            groups[normalize_public_url(str(document.canonical_url or document.url))] = group
        groups[canonical] = group
    return kept, groups
