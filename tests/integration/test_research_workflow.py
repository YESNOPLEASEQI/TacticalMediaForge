from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.schemas.video import VideoGenerateRequest
from api.tasks.models import Task, TaskStatus, TaskType
from military_video_gen.database.base import Base
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.runtime_jobs import create_runtime_job, sync_runtime_job
from military_video_gen.database.session import create_engine
from military_video_gen.research.gate import enforce_verified_storyboard_gate
from military_video_gen.research.models import (
    CrawledDocument,
    EvidenceClaim,
    EvidenceQuote,
    FieldProvenance,
    GroundedField,
    GroundedStoryboardScene,
    ResearchRequest,
    SearchCandidate,
    SubjectProfile,
    VisualFact,
)
from military_video_gen.research.service import ResearchService


class QueryPlanner:
    async def plan(self, topic, narrations):
        return ["official one", "official two", "visual traits", "operating context"]


class SearchProvider:
    async def search(self, query, *, language=None):
        return [SearchCandidate(url="https://example.org/facts", title=query)]


class CrawlProvider:
    async def crawl_many(self, candidates, *, force_refresh):
        return [
            CrawledDocument(
                url="https://example.org/facts",
                title="Facts",
                markdown="The aircraft exterior is inspected on an apron.",
                content_hash="body-hash",
                fetched_at=datetime.now(UTC),
            )
        ]


class EvidenceExtractor:
    async def extract(self, documents, sources):
        return [
            EvidenceClaim(
                id="claim-1",
                statement="The exterior is inspected on an apron.",
                subject="aircraft",
                predicate="inspection context",
                value="apron",
                source_ids=[sources[0].id],
                evidence_quotes=[
                    EvidenceQuote(
                        source_id=sources[0].id,
                        quote="exterior is inspected on an apron",
                    )
                ],
                status="partially_supported",
                confidence=0.9,
            )
        ]


class ClaimValidator:
    def clean(self, claims, sources):
        return [
            EvidenceClaim.model_validate(
                {**claim.model_dump(mode="json"), "status": "verified"}
            )
            for claim in claims
        ]


class VisualFactExtractor:
    async def extract(self, claims):
        return [
            VisualFact(
                id="visual-1",
                subject_id="subject-1",
                fact="generic exterior profile",
                claim_ids=["claim-1"],
                allowed_detail="generic military aircraft",
                forbidden_inference=["specific unit marking"],
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
        provenance = FieldProvenance(
            claim_ids=["claim-1"], visual_fact_ids=["visual-1"]
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
            [
                GroundedStoryboardScene(
                    scene_index=1,
                    narration=narrations[0],
                    asset_type=asset_type,
                    subject_id="subject-1",
                    visual_description="Verified aircraft inspection",
                    media_prompt="distinct generated aircraft inspection prompt",
                    subject=GroundedField(value="generic military aircraft", provenance=provenance),
                    environment=GroundedField(value="airbase apron", provenance=provenance),
                    opening_state=GroundedField(value="stationary", provenance=provenance),
                    action=GroundedField(value="exterior inspection", provenance=provenance),
                    camera=GroundedField(value="wide shot", creative=True),
                    composition=GroundedField(value="centered", creative=True),
                    lighting=GroundedField(value="neutral daylight", creative=True),
                    ending_frame=GroundedField(value="exterior profile", provenance=provenance),
                    claim_ids=["claim-1"],
                    visual_fact_ids=["visual-1"],
                    negative_constraints=["no logos"],
                    confidence=0.9,
                    fallback_level="verified_generic",
                    verification_status="verified",
                )
            ],
        )

def confirmed_request(snapshot, *, script_revision=4) -> VideoGenerateRequest:
    scene = snapshot.storyboard_plan[0]
    return VideoGenerateRequest(
        text=scene.narration,
        mode="fixed",
        session_id="project-a",
        frame_template="1080x1920/video_default.html",
        verification_mode="verified",
        research_topic=snapshot.topic,
        script_revision=script_revision,
        confirmed_storyboard=[
            {
                "index": scene.scene_index,
                "narration": scene.narration,
                "visual_description": scene.visual_description,
                "media_prompt": scene.media_prompt,
                "asset_type": scene.asset_type,
                "research_job_id": "research-job",
                "subject_id": scene.subject_id,
                "claim_ids": scene.claim_ids,
                "visual_fact_ids": scene.visual_fact_ids,
                "field_provenance": {
                    key: value.model_dump(mode="json")
                    for key, value in scene.field_provenance.items()
                },
                "fallback_level": scene.fallback_level,
                "verification_status": scene.verification_status,
                "negative_constraints": scene.negative_constraints,
                "warnings": scene.warnings,
            }
        ],
    )


@pytest.mark.asyncio
async def test_reference_snapshot_persists_and_gates_stale_video(tmp_path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'integration.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="Aircraft"))
        await session.commit()

    service = ResearchService(
        search_provider=SearchProvider(),
        crawl_provider=CrawlProvider(),
        query_planner=QueryPlanner(),
        evidence_extractor=EvidenceExtractor(),
        claim_validator=ClaimValidator(),
        visual_fact_extractor=VisualFactExtractor(),
        visual_planner=VisualPlanner(),
        minimum_visual_confidence=0.8,
    )
    research_request = ResearchRequest(
        project_id="project-a",
        topic="Aircraft",
        narrations=["Narration"],
        script_revision=4,
    )
    snapshot = await service.run(research_request, progress=lambda *_: None)
    assert snapshot.research_status == "reference_ready"
    assert "audit" not in snapshot.model_dump()
    assert snapshot.storyboard_plan[0].media_prompt

    task = Task(
        task_id="research-job",
        task_type=TaskType.RESEARCH,
        request_params=research_request.model_dump(mode="json"),
    )
    assert await create_runtime_job(
        project_id="project-a",
        task=task,
        job_type="research",
        factory=factory,
    )
    task.status = TaskStatus.COMPLETED
    task.result = snapshot.model_dump(mode="json")
    await sync_runtime_job(task, factory=factory)

    async with factory() as session:
        job = await session.get(GenerationJob, "research-job")
        assert "token" not in repr(job.params_json).lower()
        assert "token" not in repr(job.result_json).lower()
        await enforce_verified_storyboard_gate(session, confirmed_request(snapshot))
        with pytest.raises(HTTPException) as caught:
            await enforce_verified_storyboard_gate(
                session,
                confirmed_request(snapshot, script_revision=5),
            )
        assert caught.value.status_code == 409
    await engine.dispose()
