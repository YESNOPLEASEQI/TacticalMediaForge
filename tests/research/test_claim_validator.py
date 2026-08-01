from datetime import UTC, datetime

from military_video_gen.research.claim_validator import ClaimValidator
from military_video_gen.research.models import EvidenceClaim, EvidenceQuote, Source


def source(source_id: str, *, score: float) -> Source:
    return Source(
        id=source_id,
        url=f"https://{source_id}.example/report",
        title=source_id,
        fetched_at=datetime.now(UTC),
        content_hash=source_id,
        score=score,
    )


def claim(
    claim_id: str,
    statement: str,
    value: str,
    source_id: str,
) -> EvidenceClaim:
    return EvidenceClaim(
        id=claim_id,
        statement=statement,
        subject="missile",
        predicate="maximum speed",
        value=value,
        source_ids=[source_id],
        evidence_quotes=[EvidenceQuote(source_id=source_id, quote=statement)],
        status="partially_supported",
        confidence=0.8,
    )


def test_clean_deduplicates_claims_and_prefers_higher_quality_source() -> None:
    claims = [
        claim("low", "The vehicle uses a swept body", "swept body", "low"),
        claim("high", " The vehicle uses a swept body ", "swept body", "high"),
    ]

    cleaned = ClaimValidator().clean(
        claims,
        [source("low", score=0.4), source("high", score=0.9)],
    )

    assert len(cleaned) == 1
    assert cleaned[0].id == "high"


def test_clean_sorts_by_source_quality_and_blocks_low_quality_claims() -> None:
    cleaned = ClaimValidator().clean(
        [
            claim("low", "A broad public description", "shared", "low"),
            claim("high", "A better sourced description", "shared", "high"),
        ],
        [source("low", score=0.3), source("high", score=0.95)],
    )

    assert [item.id for item in cleaned] == ["high", "low"]
    assert cleaned[0].status == "verified"
    assert cleaned[1].status == "unsupported"


def test_clean_marks_conflicting_precise_values() -> None:
    cleaned = ClaimValidator().clean(
        [
            claim("mach-8", "Maximum speed is Mach 8", "Mach 8", "one"),
            claim("mach-12", "Maximum speed is Mach 12", "Mach 12", "two"),
        ],
        [source("one", score=0.8), source("two", score=0.8)],
    )

    assert {item.status.value for item in cleaned} == {"conflicted"}
    assert all(item.conflicts for item in cleaned)


def test_descriptive_claim_can_use_discovery_quality_source() -> None:
    descriptive = EvidenceClaim(
        id="mechanism",
        statement="Tracks spread vehicle weight across a larger contact area.",
        subject="tracks",
        predicate="spread weight",
        value="larger contact area",
        source_ids=["article"],
        evidence_quotes=[
            EvidenceQuote(
                source_id="article",
                quote="spread vehicle weight across a larger contact area",
            )
        ],
        status="partially_supported",
        confidence=0.8,
    )

    [cleaned] = ClaimValidator().clean(
        [descriptive],
        [source("article", score=0.59)],
    )

    assert cleaned.status == "low_confidence_verified"


def test_numeric_claim_still_requires_stricter_source_quality() -> None:
    [cleaned] = ClaimValidator().clean(
        [claim("weight", "The vehicle weighs 60 tonnes", "60 tonnes", "article")],
        [source("article", score=0.59)],
    )

    assert cleaned.status == "unsupported"
