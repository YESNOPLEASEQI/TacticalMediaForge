"""Non-blocking claim cleanup, conflict marking, and source-quality ordering."""

import re
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from .models import ClaimStatus, EvidenceClaim, Source

_WHITESPACE = re.compile(r"\s+")


def _normalized(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip()).casefold()


_PREDICATE_ALIASES = {
    "status": "service_status",
    "service status": "service_status",
    "operational status": "service_status",
    "current status": "service_status",
    "服役状态": "service_status",
    "现状": "service_status",
    "country": "country",
    "nation": "country",
    "country of origin": "country",
    "origin country": "country",
    "国家": "country",
    "国别": "country",
    "lifecycle": "lifecycle",
    "development status": "lifecycle",
    "production status": "lifecycle",
    "variant status": "lifecycle",
    "研制状态": "lifecycle",
    "生产状态": "lifecycle",
}
_CURRENT_VALUES = re.compile(
    r"\b(?:active|current|operational|in service|inventory|quantity)\b|现役|当前|在役|数量",
    re.IGNORECASE,
)
_STRICT_SOURCE_CLAIM = re.compile(
    r"\d|\b(?:range|height|width|length|caliber|power|thrust|"
    r"inventory|quantity|maximum|minimum|first flight|entered service|"
    r"operational effectiveness|kill probability)\b|"
    r"\u822a\u7a0b|\u9ad8\u5ea6|\u5bbd\u5ea6|"
    r"\u957f\u5ea6|\u53e3\u5f84|\u529f\u7387|\u63a8\u529b|\u6570\u91cf|"
    r"\u6700\u5927|\u6700\u5c0f|\u9996\u98de|\u670d\u5f79|\u6027\u80fd",
    re.IGNORECASE,
)


def _subject_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"^歼(?=\s*[-－]?\s*\d)", "j", normalized)
    normalized = re.sub(r"^轰(?=\s*[-－]?\s*\d)", "h", normalized)
    normalized = re.sub(r"^运(?=\s*[-－]?\s*\d)", "y", normalized)
    normalized = re.sub(r"^直(?=\s*[-－]?\s*\d)", "z", normalized)
    normalized = re.sub(r"[\s\-_－]+", "", normalized)
    return normalized


def _predicate_key(value: str) -> str:
    normalized = _normalized(value)
    return _PREDICATE_ALIASES.get(normalized, normalized)


class ClaimValidator:
    """Clean reference claims without deciding whether generation may continue."""

    def __init__(
        self,
        *,
        minimum_confidence: float = 0.75,
        minimum_low_confidence: float = 0.65,
        minimum_discovery_confidence: float = 0.55,
        current_claim_max_age_days: int = 730,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.minimum_confidence = minimum_confidence
        self.minimum_low_confidence = minimum_low_confidence
        self.minimum_discovery_confidence = minimum_discovery_confidence
        self.current_claim_max_age = timedelta(days=current_claim_max_age_days)
        self.clock = clock or (lambda: datetime.now(UTC))

    def clean(
        self,
        claims: list[EvidenceClaim],
        sources: list[Source],
    ) -> list[EvidenceClaim]:
        source_by_id = {source.id: source for source in sources}

        def quality(claim: EvidenceClaim) -> float:
            return max(
                (
                    source_by_id[source_id].score
                    for source_id in claim.source_ids
                    if source_id in source_by_id
                ),
                default=0,
            )

        def temporally_current(claim: EvidenceClaim) -> bool:
            if not _CURRENT_VALUES.search(f"{claim.predicate} {claim.value}"):
                return True
            dates = [claim.valid_at] if claim.valid_at is not None else []
            dates.extend(
                source_by_id[source_id].published_at
                for source_id in claim.source_ids
                if source_id in source_by_id and source_by_id[source_id].published_at is not None
            )
            if not dates:
                return False
            latest = max(
                date if date.tzinfo is not None else date.replace(tzinfo=UTC) for date in dates
            )
            age = self.clock() - latest
            return timedelta(0) <= age <= self.current_claim_max_age

        deduplicated: dict[str, EvidenceClaim] = {}
        for claim in claims:
            key = _normalized(claim.statement)
            current = deduplicated.get(key)
            if current is None or (quality(claim), claim.confidence) > (
                quality(current),
                current.confidence,
            ):
                preferred, other = claim, current
            else:
                preferred, other = current, claim
            if other is not None:
                preferred = preferred.model_copy(
                    update={
                        "source_ids": list(
                            dict.fromkeys([*preferred.source_ids, *other.source_ids])
                        ),
                        "evidence_quotes": list(
                            {
                                (quote.source_id, quote.quote): quote
                                for quote in [*preferred.evidence_quotes, *other.evidence_quotes]
                            }.values()
                        ),
                    }
                )
            deduplicated[key] = preferred

        cleaned = list(deduplicated.values())
        by_subject_predicate: dict[tuple[str, str], list[EvidenceClaim]] = {}
        for claim in cleaned:
            key = (_subject_key(claim.subject), _predicate_key(claim.predicate))
            by_subject_predicate.setdefault(key, []).append(claim)

        conflict_ids: dict[str, list[str]] = {}
        for group in by_subject_predicate.values():
            if len({_normalized(claim.value) for claim in group}) < 2:
                continue
            for claim in group:
                conflict_ids[claim.id] = [
                    other.id
                    for other in group
                    if other.id != claim.id and _normalized(other.value) != _normalized(claim.value)
                ]

        result = []
        for claim in cleaned:
            conflicts = list(dict.fromkeys([*claim.conflicts, *conflict_ids.get(claim.id, [])]))
            quoted_source_ids = {quote.source_id for quote in claim.evidence_quotes}
            has_server_sources = bool(claim.source_ids) and all(
                source_id in source_by_id and source_id in quoted_source_ids
                for source_id in claim.source_ids
            )
            effective_confidence = min(claim.confidence, quality(claim))
            claim_text = " ".join([claim.statement, claim.predicate, claim.value])
            minimum_supported_confidence = (
                self.minimum_low_confidence
                if _STRICT_SOURCE_CLAIM.search(claim_text)
                else min(
                    self.minimum_low_confidence,
                    self.minimum_discovery_confidence,
                )
            )
            if not temporally_current(claim):
                effective_confidence = 0
            if conflicts:
                status = ClaimStatus.CONFLICTED
            elif not has_server_sources or effective_confidence < minimum_supported_confidence:
                status = ClaimStatus.UNSUPPORTED
            elif effective_confidence < self.minimum_confidence:
                status = ClaimStatus.LOW_CONFIDENCE_VERIFIED
            else:
                status = ClaimStatus.VERIFIED
            result.append(claim.model_copy(update={"status": status, "conflicts": conflicts}))
        return sorted(result, key=lambda claim: (quality(claim), claim.confidence), reverse=True)

    def validate(
        self,
        claims: list[EvidenceClaim],
        sources: list[Source],
    ) -> list[EvidenceClaim]:
        """Backward-compatible alias for callers migrating from strict validation."""
        return self.clean(claims, sources)
