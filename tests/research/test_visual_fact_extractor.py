import pytest

from military_video_gen.research.models import EvidenceClaim, EvidenceQuote
from military_video_gen.research.visual_fact_extractor import VisualFactExtractor


class FakeLLM:
    async def generate_structured(self, *, response_type, **_kwargs):
        return response_type.model_validate(
            {
                "visual_facts": [
                    {
                        "id": "visual-1",
                        "subject_id": "subject-1",
                        "fact": "swept wing",
                        "claim_ids": ["claim-1"],
                        "allowed_detail": "swept wing silhouette",
                        "confidence": 0.55,
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_partially_supported_low_confidence_claim_cannot_produce_visual_fact() -> None:
    claim = EvidenceClaim(
        id="claim-1",
        statement="The aircraft has a swept wing.",
        subject="aircraft",
        predicate="has",
        value="swept wing",
        source_ids=["source-1"],
        evidence_quotes=[EvidenceQuote(source_id="source-1", quote="swept wing")],
        status="partially_supported",
        confidence=0.55,
    )

    facts = await VisualFactExtractor(FakeLLM(), minimum_confidence=0.8).extract(
        [claim]
    )

    assert facts == []
