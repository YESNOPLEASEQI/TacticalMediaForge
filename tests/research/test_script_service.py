from datetime import UTC, datetime

import pytest

from military_video_gen.research.models import (
    ClaimStatus,
    EvidenceClaim,
    EvidenceQuote,
    Source,
)
from military_video_gen.research.script_service import generate_researched_narrations
from military_video_gen.research.service import ReferenceMaterial, ResearchUnavailableError


def material() -> ReferenceMaterial:
    source = Source(
        id="source-1",
        url="https://example.org/report",
        title="Technical report",
        fetched_at=datetime.now(UTC),
        content_hash="hash",
        score=0.9,
    )
    claim = EvidenceClaim(
        id="claim-1",
        statement="The vehicle uses a lifting-body configuration.",
        subject="vehicle",
        predicate="uses",
        value="lifting-body configuration",
        source_ids=[source.id],
        evidence_quotes=[
            EvidenceQuote(
                source_id=source.id,
                quote="uses a lifting-body configuration",
            )
        ],
        status=ClaimStatus.PARTIALLY_SUPPORTED,
        confidence=0.8,
    )
    return ReferenceMaterial(
        queries=["vehicle technical report"],
        sources=[source],
        claims=[claim],
        visual_facts=[],
        safe_claims=[claim],
        safe_visual_facts=[],
        warnings=[],
    )


class Collector:
    async def collect_reference_material(self, request, *, progress):
        return material()


@pytest.mark.asyncio
async def test_script_generation_requires_and_injects_online_references() -> None:
    captured = {}

    async def generator(**kwargs):
        captured.update(kwargs)
        return ["第一段", "第二段"]

    result = await generate_researched_narrations(
        research_service=Collector(),
        llm_service=object(),
        project_id="project-1",
        topic="飞行器",
        n_scenes=2,
        min_words=5,
        max_words=20,
        narration_generator=generator,
    )

    assert result.narrations == ["第一段", "第二段"]
    assert result.research_status == "reference_ready"
    assert "lifting-body configuration" in captured["reference_context"]
    assert "https://example.org/report" in captured["reference_context"]
    assert captured["planning_timeout_seconds"] == 120
    assert captured["writing_timeout_seconds"] == 120


@pytest.mark.asyncio
async def test_script_generation_falls_back_without_claims() -> None:
    empty = material()
    empty = ReferenceMaterial(
        queries=empty.queries,
        sources=empty.sources,
        claims=[],
        visual_facts=[],
        safe_claims=[],
        safe_visual_facts=[],
        warnings=[],
    )

    class EmptyCollector:
        async def collect_reference_material(self, request, *, progress):
            return empty

    called = False

    async def generator(**_kwargs):
        nonlocal called
        called = True
        return ["不应生成"]

    result = await generate_researched_narrations(
        research_service=EmptyCollector(),
        llm_service=object(),
        project_id="project-1",
        topic="飞行器",
        n_scenes=1,
        min_words=5,
        max_words=20,
        narration_generator=generator,
    )

    assert called is True
    assert result.research_status == "reference_unavailable"
    assert result.warnings == ["reference_extraction_empty"]


@pytest.mark.asyncio
async def test_script_generation_falls_back_when_online_research_fails() -> None:
    class FailedCollector:
        async def collect_reference_material(self, request, *, progress):
            raise ResearchUnavailableError(
                "search_unavailable", queries=["已生成的查询"]
            )

    captured = {}

    async def generator(**kwargs):
        captured.update(kwargs)
        return ["普通生成脚本"]

    result = await generate_researched_narrations(
        research_service=FailedCollector(),
        llm_service=object(),
        project_id="project-1",
        topic="飞行器",
        n_scenes=1,
        min_words=5,
        max_words=20,
        narration_generator=generator,
    )

    assert result.narrations == ["普通生成脚本"]
    assert result.research_status == "reference_unavailable"
    assert result.queries == ["已生成的查询"]
    assert result.sources == []
    assert result.warnings == ["search_unavailable"]
    assert "reference_context" not in captured


@pytest.mark.asyncio
async def test_required_reference_mode_does_not_generate_an_ungrounded_script() -> None:
    class FailedCollector:
        async def collect_reference_material(self, request, *, progress):
            raise ResearchUnavailableError(
                "search_unavailable",
                queries=["F-16 official history"],
            )

    called = False

    async def generator(**_kwargs):
        nonlocal called
        called = True
        return ["ungrounded narration"]

    with pytest.raises(ResearchUnavailableError, match="search_unavailable"):
        await generate_researched_narrations(
            research_service=FailedCollector(),
            llm_service=object(),
            project_id="project-1",
            topic="F-16 history",
            n_scenes=1,
            min_words=5,
            max_words=20,
            narration_generator=generator,
            require_references=True,
        )

    assert called is False
