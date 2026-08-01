import pytest
from pydantic import ValidationError

from military_video_gen.research.models import (
    ClaimStatus,
    EvidenceClaim,
    EvidenceQuote,
    GroundedField,
    GroundedStoryboardScene,
    VerificationStatus,
)


def test_low_confidence_statuses_are_serializable() -> None:
    assert ClaimStatus.LOW_CONFIDENCE_VERIFIED.value == "low_confidence_verified"
    assert (
        VerificationStatus.LOW_CONFIDENCE_VERIFIED.value
        == "low_confidence_verified"
    )


def test_generic_safe_factual_fields_do_not_require_provenance() -> None:
    scene = GroundedStoryboardScene(
        scene_index=1,
        narration="Narration",
        subject=GroundedField(
            value="generic military technology silhouette",
            generic_safe=True,
        ),
        environment=GroundedField(
            value="neutral non-specific display environment",
            generic_safe=True,
        ),
        opening_state=GroundedField(value="static display", generic_safe=True),
        action=GroundedField(value="slow observational view", generic_safe=True),
        camera=GroundedField(value="wide shot", creative=True),
        composition=GroundedField(value="centered composition", creative=True),
        lighting=GroundedField(value="neutral lighting", creative=True),
        ending_frame=GroundedField(
            value="neutral wide profile",
            generic_safe=True,
        ),
        fallback_level="generic_safe",
        verification_status="insufficient_evidence",
    )

    assert scene.subject.generic_safe is True


def test_claim_requires_at_least_one_source_quote() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            id="claim-1",
            statement="The aircraft has a swept wing.",
            subject="aircraft",
            predicate="has",
            value="swept wing",
            source_ids=["source-1"],
            evidence_quotes=[],
            status="verified",
            confidence=0.9,
        )


def test_evidence_quote_must_contain_verbatim_text() -> None:
    with pytest.raises(ValidationError):
        EvidenceQuote(source_id="source-1", quote="", location="paragraph 2")


def test_factual_scene_fields_do_not_require_provenance() -> None:
    factual = GroundedField(value="generic military aircraft")

    scene = GroundedStoryboardScene(
        scene_index=1,
        narration="Narration",
        visual_description="Aircraft on apron",
        subject=factual,
        environment=GroundedField(value="airbase apron", creative=True),
        opening_state=GroundedField(value="stationary", creative=True),
        action=GroundedField(value="crew inspect exterior", creative=True),
        camera=GroundedField(value="wide shot", creative=True),
        composition=GroundedField(value="centered", creative=True),
        lighting=GroundedField(value="neutral daylight", creative=True),
        ending_frame=GroundedField(value="exterior profile", creative=True),
        fallback_level="verified_specific",
        verification_status=VerificationStatus.VERIFIED,
    )

    assert scene.subject.provenance is None
