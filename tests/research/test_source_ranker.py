from datetime import UTC, datetime

from military_video_gen.research.claim_validator import ClaimValidator
from military_video_gen.research.models import (
    CrawledDocument,
    EvidenceClaim,
    EvidenceQuote,
    Source,
)
from military_video_gen.research.source_ranker import (
    deduplicate_documents,
    score_claim_source,
)


def document(url: str, body: str, content_hash: str) -> CrawledDocument:
    return CrawledDocument(
        url=url,
        title="Document",
        markdown=body,
        content_hash=content_hash,
        fetched_at=datetime.now(UTC),
    )


def test_deduplication_groups_canonical_and_identical_content() -> None:
    docs = [
        document("https://a.example/report?utm_source=x", "same body", "hash-1"),
        document("https://a.example/report", "same body", "hash-1"),
        document("https://mirror.example/repost", "same body", "hash-1"),
        document("https://independent.example/report", "different body", "hash-2"),
    ]

    kept, groups = deduplicate_documents(docs)

    assert len(kept) == 2
    assert groups["https://mirror.example/repost"] == groups["https://a.example/report"]
    assert groups["https://independent.example/report"] != groups["https://a.example/report"]


def test_manufacturer_operational_claim_is_downweighted() -> None:
    source = Source(
        id="source-1",
        url="https://manufacturer.example/product",
        title="Product",
        source_type="manufacturer",
        fetched_at=datetime.now(UTC),
        content_hash="hash",
    )

    dimensions = score_claim_source(source, claim_kind="dimensions")
    operational = score_claim_source(source, claim_kind="operational_effectiveness")

    assert dimensions > operational
    assert 0 <= operational <= 1


def test_unknown_single_source_cannot_become_verified_through_fixed_bonuses() -> None:
    source = Source(
        id="random-blog",
        url="https://random-blog.example/post",
        title="Random blog",
        source_type="other",
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        content_hash="random",
        independence_group="random-blog.example",
    )
    source.score = score_claim_source(source, claim_kind="public_fact")
    claim = EvidenceClaim(
        id="fabricated",
        statement="ZX-999 has range 5000 km",
        subject="ZX-999",
        predicate="range",
        value="5000 km",
        source_ids=[source.id],
        evidence_quotes=[EvidenceQuote(source_id=source.id, quote="range 5000 km")],
        status="partially_supported",
        confidence=0.95,
    )

    [cleaned] = ClaimValidator().clean([claim], [source])

    assert source.score < 0.65
    assert cleaned.status.value == "unsupported"
