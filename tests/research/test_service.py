import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from api.schemas.video import VideoGenerateRequest
from military_video_gen.research.gate import enforce_verified_storyboard_gate
from military_video_gen.research.models import (
    ClaimStatus,
    EvidenceClaim,
    EvidenceQuote,
    FieldProvenance,
    GroundedField,
    GroundedStoryboardScene,
    ResearchRequest,
    SearchCandidate,
    Source,
    SourceType,
    SubjectProfile,
    VisualFact,
)
from military_video_gen.research.providers.searxng import SearchUnavailableError
from military_video_gen.research.service import ResearchService, _source_type


def test_lockheed_martin_is_classified_as_manufacturer() -> None:
    assert (
        _source_type("https://www.lockheedmartin.com/en-us/products/f-16.html")
        is SourceType.MANUFACTURER
    )


def test_mainstream_articles_and_reference_sites_are_classified() -> None:
    assert _source_type("https://www.163.com/dy/article/example.html") is SourceType.NEWS
    assert _source_type("https://baike.baidu.com/item/example") is SourceType.REFERENCE


def test_candidate_limit_prefers_recognized_manufacturer() -> None:
    service = ResearchService.__new__(ResearchService)
    service.max_pages = 1
    service.max_pages_per_domain = 2
    candidates = [
        SearchCandidate(
            url="https://random.example/f-16",
            title="F-16 fighter aircraft history",
            snippet="first flight design",
            query="F-16",
        ),
        SearchCandidate(
            url="https://www.lockheedmartin.com/en-us/products/f-16.html",
            title="F-16 fighter aircraft history",
            snippet="first flight design",
            query="F-16",
        ),
    ]

    selected = service._limit_candidates(
        candidates,
        topic="F-16 fighter aircraft",
        narrations=["F-16 first flight design"],
    )

    assert str(selected[0].url).startswith("https://www.lockheedmartin.com/")


def test_candidate_limit_prefers_manufacturer_history_over_press_release() -> None:
    service = ResearchService.__new__(ResearchService)
    service.max_pages = 1
    service.max_pages_per_domain = 2
    candidates = [
        SearchCandidate(
            url="https://news.lockheedmartin.com/f-16-test-aircraft-first-flight",
            title="F-16 Test Aircraft First Flight",
            snippet="test aircraft first flight details",
            query="F-16",
        ),
        SearchCandidate(
            url="https://www.lockheedmartin.com/en-us/news/features/history/f16.html",
            title="F-16 Fighting Falcon History",
            snippet="design history",
            query="F-16",
        ),
    ]

    selected = service._limit_candidates(
        candidates,
        topic="F-16 fighter aircraft history",
        narrations=["F-16 design and visible appearance"],
    )

    assert "/history/" in str(selected[0].url)


class Search:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def search(self, query: str, *, language=None):
        if self.fail:
            raise SearchUnavailableError("offline")
        return [SearchCandidate(url="https://example.org/report", title=query)]


class Crawl:
    def __init__(self, docs: list) -> None:
        self.docs = docs

    async def crawl_many(self, candidates, *, force_refresh):
        return self.docs


class Planner:
    async def plan(self, topic, narrations):
        return ["one", "two", "three", "four"]


class Extractor:
    async def extract(self, documents, sources):
        return [
            EvidenceClaim(
                id="claim-1",
                statement="Aircraft exterior narration fact",
                subject="aircraft",
                predicate="has",
                value="exterior",
                source_ids=[sources[0].id],
                evidence_quotes=[EvidenceQuote(source_id=sources[0].id, quote="verified body")],
                status="partially_supported",
                confidence=0.9,
            )
        ]


class Validator:
    def clean(self, claims, sources):
        return [claim.model_copy(update={"status": ClaimStatus.VERIFIED}) for claim in claims]


class FactExtractor:
    async def extract(self, claims):
        return [
            VisualFact(
                id="visual-1",
                subject_id="subject-1",
                fact="generic exterior",
                claim_ids=["claim-1"],
                allowed_detail="generic military aircraft",
                confidence=0.9,
            )
        ]


class VisualPlanner:
    async def plan(
        self,
        narrations,
        subject_profiles,
        visual_facts,
        asset_type,
        research_claims=None,
    ):
        del research_claims
        provenance = FieldProvenance(claim_ids=["claim-1"], visual_fact_ids=["visual-1"])
        scene = GroundedStoryboardScene(
            scene_index=1,
            narration=narrations[0],
            media_prompt="distinct generated scene prompt",
            asset_type=asset_type,
            subject_id="subject-1",
            subject=GroundedField(value="generic military aircraft", provenance=provenance),
            environment=GroundedField(value="airbase apron", provenance=provenance),
            opening_state=GroundedField(value="stationary", provenance=provenance),
            action=GroundedField(value="exterior inspection", provenance=provenance),
            camera=GroundedField(value="wide shot", creative=True),
            composition=GroundedField(value="centered", creative=True),
            lighting=GroundedField(value="daylight", creative=True),
            ending_frame=GroundedField(value="exterior profile", provenance=provenance),
            claim_ids=["claim-1"],
            visual_fact_ids=["visual-1"],
            negative_constraints=["no logos"],
            confidence=0.9,
            fallback_level="verified_generic",
            verification_status="verified",
        )
        return (
            [
                SubjectProfile(
                    id="subject-1",
                    canonical_name="generic aircraft",
                    category="aircraft",
                    generic_fallback={"category": "generic aircraft"},
                )
            ],
            [scene],
        )


def request() -> ResearchRequest:
    return ResearchRequest(
        project_id="project-1",
        topic="aircraft",
        narrations=["Aircraft exterior narration"],
        script_revision=3,
    )


def service(
    search,
    crawl,
    *,
    total_timeout=5,
    extraction_timeout=60,
    planning_timeout=30,
) -> ResearchService:
    return ResearchService(
        search_provider=search,
        crawl_provider=crawl,
        query_planner=Planner(),
        evidence_extractor=Extractor(),
        claim_validator=Validator(),
        visual_fact_extractor=FactExtractor(),
        visual_planner=VisualPlanner(),
        minimum_visual_confidence=0.8,
        total_timeout_seconds=total_timeout,
        extraction_timeout_seconds=extraction_timeout,
        planning_timeout_seconds=planning_timeout,
    )


@pytest.mark.asyncio
async def test_successful_service_renders_prompts_without_audit_phase() -> None:
    from military_video_gen.research.models import CrawledDocument

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    phases = []

    snapshot = await service(Search(), Crawl(docs)).run(
        request(), progress=lambda phase, current, total: phases.append(phase)
    )

    assert snapshot.research_status == "reference_ready"
    assert snapshot.verification_status == "verified"
    assert "audit" not in snapshot.model_dump()
    assert snapshot.storyboard_plan[0].media_prompt
    assert "auditing" not in phases
    assert "rendering_prompts" in phases


@pytest.mark.asyncio
async def test_production_planner_snapshot_passes_verified_gate() -> None:
    from military_video_gen.research.models import CrawledDocument
    from military_video_gen.research.visual_planner import VisualPlanner as ProductionPlanner

    class PromptLLM:
        async def __call__(self, **_kwargs):
            return json.dumps(
                {
                    "video_prompts": [
                        "Documentary close view states the aircraft has six engines, "
                        "twelve nuclear missiles, red national insignia, and operates "
                        "from a named frontline airbase, all shown as authentic details."
                    ]
                }
            )

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.visual_planner = ProductionPlanner(PromptLLM())
    research_request = request()
    snapshot = await research.run(research_request, progress=lambda *_: None)
    scene = snapshot.storyboard_plan[0]
    required = {"subject", "environment", "opening_state", "action", "ending_frame"}
    assert required.issubset(scene.field_provenance)
    assert scene.subject.value == "aircraft"
    assert scene.subject.provenance is not None
    assert scene.subject.provenance.claim_ids == ["claim-1"]
    for field_name in required - {"subject"}:
        field = getattr(scene, field_name)
        provenance = scene.field_provenance[field_name]
        assert field.value
        assert field.generic_safe is True
        assert provenance.creative is True
        assert provenance.claim_ids == []
        assert provenance.visual_fact_ids == []
    retained = ("six engines", "nuclear missiles", "red national", "frontline airbase")
    assert all(value in scene.media_prompt.casefold() for value in retained)
    assert scene.media_prompt == scene.visual_description
    assert "generic non-identifying military environment" not in scene.media_prompt
    assert scene.negative_constraints == []

    research_job_id = "research-1"
    confirmed = {
        "index": scene.scene_index,
        "narration": scene.narration,
        "visual_description": scene.visual_description,
        "media_prompt": scene.media_prompt,
        "estimated_duration": scene.estimated_duration,
        "asset_type": scene.asset_type,
        "research_job_id": research_job_id,
        "subject_id": scene.subject_id,
        "claim_ids": scene.claim_ids,
        "visual_fact_ids": scene.visual_fact_ids,
        "field_provenance": {
            name: provenance.model_dump(mode="json")
            for name, provenance in scene.field_provenance.items()
        },
        "fallback_level": scene.fallback_level,
        "verification_status": scene.verification_status,
        "negative_constraints": scene.negative_constraints,
        "warnings": scene.warnings,
    }
    generation_request = VideoGenerateRequest(
        text=scene.narration,
        mode="fixed",
        session_id=research_request.project_id,
        verification_mode="verified",
        research_topic=research_request.topic,
        script_revision=research_request.script_revision,
        confirmed_storyboard=[confirmed],
    )
    project = SimpleNamespace(
        id=research_request.project_id,
        deleted_at=None,
        settings_json={"active_research_job_id": research_job_id},
    )
    job = SimpleNamespace(
        id=research_job_id,
        project_id=research_request.project_id,
        job_type="research",
        status="completed",
        result_json=snapshot.model_dump(mode="json"),
    )

    class FakeSession:
        async def get(self, model, _identifier):
            return project if model.__name__ == "Project" else job

    await enforce_verified_storyboard_gate(FakeSession(), generation_request)


@pytest.mark.asyncio
async def test_low_confidence_claims_are_explicitly_labelled() -> None:
    from military_video_gen.research.models import CrawledDocument

    class LowConfidenceValidator:
        def clean(self, claims, sources):
            return [
                claim.model_copy(
                    update={
                        "status": ClaimStatus.LOW_CONFIDENCE_VERIFIED,
                        "confidence": 0.67,
                    }
                )
                for claim in claims
            ]

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.claim_validator = LowConfidenceValidator()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.verification_status == "low_confidence_verified"
    assert snapshot.storyboard_plan[0].verification_status == "low_confidence_verified"
    assert "single_source_verification" not in snapshot.warnings
    assert "single_source_verification" not in snapshot.storyboard_plan[0].warnings
    assert snapshot.research_status == "reference_ready"
    assert "audit" not in snapshot.model_dump()


@pytest.mark.asyncio
async def test_all_search_queries_failed_generates_ordinary_storyboard() -> None:
    snapshot = await service(Search(fail=True), Crawl([])).run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["search_unavailable"]
    assert snapshot.sources == []
    assert snapshot.storyboard_plan[0].media_prompt


@pytest.mark.asyncio
async def test_no_crawled_documents_generates_ordinary_storyboard() -> None:
    snapshot = await service(Search(), Crawl([])).run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["all_crawls_failed"]
    assert snapshot.storyboard_plan[0].media_prompt


@pytest.mark.asyncio
async def test_no_visual_facts_still_generates_storyboard() -> None:
    from military_video_gen.research.models import CrawledDocument

    class EmptyFactExtractor:
        async def extract(self, claims):
            return []

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.visual_fact_extractor = EmptyFactExtractor()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.verification_status == "verified"
    assert snapshot.research_status == "reference_ready"
    assert len(snapshot.storyboard_plan) == 1
    assert snapshot.storyboard_plan[0].fallback_level == "verified_generic"
    assert snapshot.storyboard_plan[0].generic_fallback is None
    assert "no_visual_research_notes" not in snapshot.warnings
    assert "audit" not in snapshot.model_dump()


@pytest.mark.asyncio
async def test_no_usable_reference_notes_generates_ordinary_storyboard() -> None:
    from military_video_gen.research.models import CrawledDocument

    class EmptyEvidenceExtractor:
        async def extract(self, documents, sources):
            return []

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="page without extractable reference notes",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.evidence_extractor = EmptyEvidenceExtractor()

    snapshot = await research.run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["reference_extraction_empty"]
    assert snapshot.queries
    assert snapshot.sources
    assert snapshot.storyboard_plan[0].media_prompt


@pytest.mark.asyncio
async def test_llm_insufficient_balance_is_reported_precisely() -> None:
    from military_video_gen.research.models import CrawledDocument

    class InsufficientBalanceError(RuntimeError):
        status_code = 402

    class BalanceFailureExtractor:
        async def extract(self, documents, sources):
            raise InsufficientBalanceError("Insufficient Balance")

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="An explicit source fact.",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.evidence_extractor = BalanceFailureExtractor()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["llm_insufficient_balance"]


@pytest.mark.asyncio
async def test_cancelled_error_is_not_converted_to_failure() -> None:
    class CancelledSearch:
        async def search(self, query, *, language=None):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await service(CancelledSearch(), Crawl([])).run(request(), progress=lambda *_: None)


@pytest.mark.asyncio
async def test_total_timeout_generates_ordinary_storyboard() -> None:
    class SlowPlanner:
        async def plan(self, topic, narrations):
            await asyncio.sleep(0.02)

    research = service(Search(), Crawl([]), total_timeout=0.001)
    research.query_planner = SlowPlanner()

    snapshot = await research.run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["reference_timeout"]
    assert snapshot.storyboard_plan[0].media_prompt


@pytest.mark.asyncio
async def test_storyboard_planning_timeout_completes_with_local_fallback() -> None:
    from military_video_gen.research.models import CrawledDocument

    class SlowVisualPlanner(VisualPlanner):
        async def plan(self, *args, **kwargs):
            await asyncio.sleep(0.02)

        fallback_plan = staticmethod(
            lambda narrations, asset_type: VisualPlannerFallback.fallback_plan(
                narrations, asset_type
            )
        )

    class VisualPlannerFallback:
        @staticmethod
        def fallback_plan(narrations, asset_type):
            scene = GroundedStoryboardScene(
                scene_index=1,
                narration=narrations[0],
                media_prompt="fact-neutral local fallback scene",
                asset_type=asset_type,
                subject=GroundedField(),
                environment=GroundedField(),
                opening_state=GroundedField(),
                action=GroundedField(),
                camera=GroundedField(),
                composition=GroundedField(),
                lighting=GroundedField(),
                ending_frame=GroundedField(),
                fallback_level="unverified",
                verification_status="unverified",
            )
            return [], [scene]

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs), planning_timeout=0.001)
    research.visual_planner = SlowVisualPlanner()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["storyboard_planning_timeout"]
    assert snapshot.sources
    assert snapshot.storyboard_plan[0].media_prompt == "fact-neutral local fallback scene"


@pytest.mark.asyncio
async def test_storyboard_planning_timeout_retries_as_ordinary_generation() -> None:
    from military_video_gen.research.models import CrawledDocument

    class RetryingVisualPlanner(VisualPlanner):
        async def plan(self, *args, **kwargs):
            await asyncio.sleep(0.02)

        async def plan_ordinary(self, narrations, asset_type):
            scene = GroundedStoryboardScene(
                scene_index=1,
                narration=narrations[0],
                media_prompt="Wide view of an aircraft as it taxis to a stable stop.",
                asset_type=asset_type,
                subject=GroundedField(),
                environment=GroundedField(),
                opening_state=GroundedField(),
                action=GroundedField(),
                camera=GroundedField(),
                composition=GroundedField(),
                lighting=GroundedField(),
                ending_frame=GroundedField(),
                fallback_level="unverified",
                verification_status="unverified",
            )
            return [], [scene]

        @staticmethod
        def fallback_plan(*_args, **_kwargs):
            raise AssertionError("local fallback should not be used")

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Aircraft exterior report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs), planning_timeout=0.005)
    research.visual_planner = RetryingVisualPlanner()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["storyboard_planning_timeout"]
    assert "aircraft" in snapshot.storyboard_plan[0].media_prompt


def test_same_name_person_claims_are_removed_from_cannon_references() -> None:
    now = datetime.now(UTC)
    sources = [
        Source(
            id="source-person",
            url="https://example.org/person",
            title="大炮：中国内地配音男演员",
            fetched_at=now,
            content_hash="person",
        ),
        Source(
            id="source-cannon",
            url="https://example.org/cannon",
            title="火炮炮管与弹丸的工作原理",
            fetched_at=now,
            content_hash="cannon",
        ),
    ]
    claims = [
        EvidenceClaim(
            id="person",
            statement="大炮的职业是中国内地CV",
            subject="大炮",
            predicate="职业",
            value="中国内地CV",
            source_ids=["source-person"],
            evidence_quotes=[EvidenceQuote(source_id="source-person", quote="职业：CV")],
            status="partially_supported",
            confidence=0.9,
        ),
        EvidenceClaim(
            id="cannon",
            statement="火药产生高压气体并推动弹丸穿过炮管",
            subject="大炮",
            predicate="工作原理",
            value="高压气体推动弹丸",
            source_ids=["source-cannon"],
            evidence_quotes=[EvidenceQuote(source_id="source-cannon", quote="推动弹丸")],
            status="partially_supported",
            confidence=0.85,
        ),
    ]
    research = service(Search(), Crawl([]))

    filtered = research._filter_relevant_claims(
        claims,
        sources,
        topic="大炮",
        narrations=["火药推动弹丸穿过炮管，膛线让弹丸保持稳定。"],
    )

    assert [claim.id for claim in filtered] == ["cannon"]


def test_manufacturer_identifier_supports_cross_language_relevance() -> None:
    now = datetime.now(UTC)
    source = Source(
        id="source-f16",
        url="https://www.lockheedmartin.com/en-us/news/features/history/f16.html",
        title="F-16 Fighting Falcon History | Lockheed Martin",
        source_type=SourceType.MANUFACTURER,
        fetched_at=now,
        content_hash="f16",
        score=0.8,
    )
    claim = EvidenceClaim(
        id="claim-f16",
        statement="The design featured a blended wing/body configuration.",
        subject="the design",
        predicate="featured",
        value="a blended wing/body configuration",
        source_ids=[source.id],
        evidence_quotes=[
            EvidenceQuote(
                source_id=source.id,
                quote="a blended wing/body configuration",
            )
        ],
        status="verified",
        confidence=0.9,
    )
    research = service(Search(), Crawl([]))

    filtered = research._filter_relevant_claims(
        [claim],
        [source],
        topic="F-16战斗机基础科普",
        narrations=["介绍其典型外观特征。"],
    )

    assert [item.id for item in filtered] == ["claim-f16"]


def test_scene_year_must_match_the_linked_verified_claim() -> None:
    claim = EvidenceClaim(
        id="claim-1978",
        statement="The test aircraft first flew in April 1978.",
        subject="F-16 test aircraft",
        predicate="first flew",
        value="April 1978",
        source_ids=["source-1"],
        evidence_quotes=[EvidenceQuote(source_id="source-1", quote="first flew in April 1978")],
        status="verified",
        confidence=1.0,
    )
    scene = GroundedStoryboardScene(
        scene_index=1,
        narration="1974年F-16完成首次试飞",
        media_prompt="F-16 documentary view",
        asset_type="video",
        subject=GroundedField(),
        environment=GroundedField(),
        opening_state=GroundedField(),
        action=GroundedField(),
        camera=GroundedField(),
        composition=GroundedField(),
        lighting=GroundedField(),
        ending_frame=GroundedField(),
        claim_ids=[claim.id],
        fallback_level="unverified",
        verification_status="unverified",
    )
    request_with_wrong_year = ResearchRequest(
        project_id="project-1",
        topic="F-16",
        narrations=[scene.narration],
        asset_type="video",
    )

    ResearchService._normalize_generated_scenes(
        request_with_wrong_year,
        [scene],
        {claim.id: claim},
    )

    assert scene.claim_ids == []
    assert scene.verification_status == "insufficient_evidence"


def test_normalization_preserves_distinct_creative_prompts_for_the_same_subject() -> None:
    claim = EvidenceClaim(
        id="claim-1",
        statement="Tracked vehicles spread their weight over a larger contact area.",
        subject="tank",
        predicate="uses",
        value="tracks",
        source_ids=["source-1"],
        evidence_quotes=[
            EvidenceQuote(
                source_id="source-1",
                quote="spread their weight over a larger contact area",
            )
        ],
        confidence=0.9,
        status="verified",
    )
    prompts = [
        "A low tracking shot follows a tank crossing deep mud as its steel track links press a broad path into the wet ground.",
        "A macro side view studies individual tank track links rolling around the drive sprocket while compacted soil falls away.",
    ]
    narrations = ["坦克在泥地中前进", "履带绕过主动轮"]
    scenes = [
        GroundedStoryboardScene(
            scene_index=index,
            narration=narration,
            media_prompt=prompt,
            visual_description=prompt,
            asset_type="video",
            subject=GroundedField(),
            environment=GroundedField(),
            opening_state=GroundedField(),
            action=GroundedField(),
            camera=GroundedField(),
            composition=GroundedField(),
            lighting=GroundedField(),
            ending_frame=GroundedField(),
            claim_ids=[claim.id],
            fallback_level="unverified",
            verification_status="unverified",
        )
        for index, (narration, prompt) in enumerate(
            zip(narrations, prompts, strict=True),
            start=1,
        )
    ]
    research_request = ResearchRequest(
        project_id="project-1",
        topic="坦克履带",
        narrations=narrations,
        asset_type="video",
    )

    ResearchService._normalize_generated_scenes(
        research_request,
        scenes,
        {claim.id: claim},
    )

    assert [scene.media_prompt for scene in scenes] == prompts
    assert len({scene.media_prompt for scene in scenes}) == 2
    assert all(scene.subject.value == "tank" for scene in scenes)


@pytest.mark.asyncio
async def test_evidence_extraction_timeout_generates_ordinary_storyboard() -> None:
    from military_video_gen.research.models import CrawledDocument

    class SlowExtractor:
        async def extract(self, documents, sources):
            await asyncio.sleep(0.02)

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(
        Search(),
        Crawl(docs),
        total_timeout=5,
        extraction_timeout=0.001,
    )
    research.evidence_extractor = SlowExtractor()

    snapshot = await research.run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "reference_unavailable"
    assert snapshot.warnings == ["reference_timeout"]
    assert snapshot.storyboard_plan[0].media_prompt


@pytest.mark.asyncio
async def test_one_failed_query_uses_other_search_results() -> None:
    from military_video_gen.research.models import CrawledDocument

    class FiveQueryPlanner:
        async def plan(self, topic, narrations):
            return ["one", "two", "three", "four", "five"]

    class PartlyFailingSearch(Search):
        async def search(self, query, *, language=None):
            if query == "three":
                raise SearchUnavailableError("offline")
            return await super().search(query, language=language)

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(PartlyFailingSearch(), Crawl(docs))
    research.query_planner = FiveQueryPlanner()
    snapshot = await research.run(request(), progress=lambda *_: None)
    assert snapshot.research_status == "partial_reference"
    assert snapshot.warnings == ["partial_search_failure"]
    assert snapshot.sources


@pytest.mark.asyncio
async def test_inconsistent_visual_references_are_removed_before_generation() -> None:
    from military_video_gen.research.models import CrawledDocument

    class BrokenVisualPlanner(VisualPlanner):
        async def plan(
            self,
            narrations,
            subject_profiles,
            visual_facts,
            asset_type,
            research_claims=None,
        ):
            profiles, scenes = await super().plan(
                narrations,
                subject_profiles,
                visual_facts,
                asset_type,
                research_claims,
            )
            scenes[0].visual_fact_ids = ["missing"]
            return profiles, scenes

    docs = [
        CrawledDocument(
            url="https://example.org/report",
            title="Report",
            markdown="verified body",
            content_hash="hash",
            fetched_at=datetime.now(UTC),
        )
    ]
    research = service(Search(), Crawl(docs))
    research.visual_planner = BrokenVisualPlanner()

    snapshot = await research.run(request(), progress=lambda *_: None)

    assert snapshot.storyboard_plan[0].visual_fact_ids == []
    assert snapshot.storyboard_plan[0].media_prompt
