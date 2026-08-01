"""Server-side authorization gate for verified storyboard generation."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from military_video_gen.database.models import GenerationJob, Project

from .freshness import compute_input_hash
from .models import (
    ClaimStatus,
    GroundedStoryboardScene,
    ResearchSnapshot,
    ResearchStatus,
    VerificationStatus,
)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=409, detail=message)


def _scene_matches(confirmed, grounded: GroundedStoryboardScene) -> bool:
    expected_provenance = {
        name: provenance.model_dump(mode="json")
        for name, provenance in grounded.field_provenance.items()
    }
    actual_provenance = {
        name: provenance.model_dump(mode="json")
        for name, provenance in confirmed.field_provenance.items()
    }
    return all(
        (
            confirmed.narration == grounded.narration,
            confirmed.visual_description == grounded.visual_description,
            confirmed.media_prompt == grounded.media_prompt,
            confirmed.asset_type == grounded.asset_type,
            confirmed.subject_id == grounded.subject_id,
            confirmed.claim_ids == grounded.claim_ids,
            confirmed.visual_fact_ids == grounded.visual_fact_ids,
            actual_provenance == expected_provenance,
            confirmed.fallback_level == grounded.fallback_level,
            confirmed.verification_status == grounded.verification_status,
            confirmed.negative_constraints == grounded.negative_constraints,
            confirmed.warnings == grounded.warnings,
        )
    )


async def enforce_verified_storyboard_gate(session: AsyncSession, request) -> None:
    """Validate ownership, freshness, evidence status, and exact provenance."""
    if request.verification_mode != "verified":
        return
    if not request.session_id:
        raise _conflict("verified generation requires a project session_id")
    scenes = request.confirmed_storyboard or []
    if not scenes:
        raise _conflict("verified generation requires a confirmed storyboard")
    research_ids = {scene.research_job_id for scene in scenes}
    if None in research_ids or len(research_ids) != 1:
        raise _conflict("all verified scenes must reference the same research job")
    research_job_id = next(iter(research_ids))

    project = await session.get(Project, request.session_id)
    if project is None or project.deleted_at is not None:
        raise _conflict("verified research project was not found")
    if (project.settings_json or {}).get("active_research_job_id") != research_job_id:
        raise _conflict("referenced research is not the project's active research")
    job = await session.get(GenerationJob, research_job_id)
    if (
        job is None
        or job.project_id != project.id
        or job.job_type != "research"
        or job.status not in {"completed", "success"}
    ):
        raise _conflict("referenced research job is not a completed project research job")
    try:
        snapshot = ResearchSnapshot.model_validate(job.result_json)
    except (TypeError, ValueError) as error:
        raise _conflict("research snapshot is invalid") from error
    if snapshot.research_status not in {
        ResearchStatus.REFERENCE_READY,
        ResearchStatus.PARTIAL_REFERENCE,
    }:
        if "llm_insufficient_balance" in snapshot.warnings:
            raise _conflict("research LLM has insufficient balance")
        if "llm_authentication_failed" in snapshot.warnings:
            raise _conflict("research LLM authentication failed")
        if "llm_endpoint_or_model_not_found" in snapshot.warnings:
            raise _conflict("research LLM endpoint or model was not found")
        raise _conflict("research snapshot is not ready")
    if snapshot.verification_status in {
        VerificationStatus.INSUFFICIENT_EVIDENCE,
        VerificationStatus.UNVERIFIED,
    }:
        raise _conflict("research snapshot is not confirmable")
    eligible_claim_ids = {
        claim.id
        for claim in snapshot.claims
        if claim.status
        in {ClaimStatus.VERIFIED, ClaimStatus.LOW_CONFIDENCE_VERIFIED}
        and not claim.conflicts
    }
    eligible_visual_fact_ids = {
        fact.id
        for fact in snapshot.visual_facts
        if fact.claim_ids
        and set(fact.claim_ids).issubset(eligible_claim_ids)
    }
    if not snapshot.sources or not eligible_claim_ids:
        raise _conflict("research snapshot has no usable server-owned evidence")
    if request.script_revision is None or request.script_revision != snapshot.script_revision:
        raise _conflict("research is stale because the script revision changed")
    current_hash = compute_input_hash(
        topic=request.research_topic or "",
        narrations=[scene.narration for scene in scenes],
        asset_type=scenes[0].asset_type,
        mode="verified",
    )
    if current_hash != snapshot.input_hash:
        raise _conflict("research is stale because its inputs changed")

    snapshot_scenes = {scene.scene_index: scene for scene in snapshot.storyboard_plan}
    for position, scene in enumerate(scenes, start=1):
        if scene.verification_status in {
            VerificationStatus.INSUFFICIENT_EVIDENCE,
            VerificationStatus.UNVERIFIED,
        }:
            raise _conflict(f"scene {scene.index} is not verified")
        if not scene.claim_ids or not set(scene.claim_ids).issubset(eligible_claim_ids):
            raise _conflict(f"scene {scene.index} references unsupported claims")
        grounded = snapshot_scenes.get(scene.index) or snapshot_scenes.get(position)
        candidates = [grounded] if grounded is not None else []
        if grounded is not None and grounded.generic_fallback is not None:
            candidates.append(grounded.generic_fallback)
        matched_grounded = next(
            (candidate for candidate in candidates if _scene_matches(scene, candidate)),
            None,
        )
        if matched_grounded is None:
            raise _conflict(f"scene {scene.index} differs from its research snapshot")
        grounded = matched_grounded

        required = {"subject", "environment", "opening_state", "action", "ending_frame"}
        if not required.issubset(scene.field_provenance):
            raise _conflict(f"scene {scene.index} lacks required field classification")
        if grounded is None:
            raise _conflict(f"scene {scene.index} is absent from its research snapshot")
        evidence_backed_fields = 0
        for field_name in required:
            provenance = scene.field_provenance[field_name]
            grounded_field = getattr(grounded, field_name)
            if grounded_field.provenance is None:
                if (
                    provenance.creative
                    and not provenance.claim_ids
                    and not provenance.visual_fact_ids
                    and grounded_field.creative
                    and grounded_field.generic_safe
                    and grounded_field.value.strip()
                ):
                    continue
                raise _conflict(
                    f"scene {scene.index} field {field_name} is neither evidenced nor generic-safe"
                )
            if (
                provenance.creative
                or not grounded_field.value.strip()
                or not (provenance.claim_ids or provenance.visual_fact_ids)
            ):
                raise _conflict(f"scene {scene.index} field {field_name} lacks evidence mapping")
            if not set(provenance.claim_ids).issubset(eligible_claim_ids):
                raise _conflict(
                    f"scene {scene.index} field {field_name} references unsupported claims"
                )
            if not set(provenance.visual_fact_ids).issubset(eligible_visual_fact_ids):
                raise _conflict(
                    f"scene {scene.index} field {field_name} references unsupported visual facts"
                )
            evidence_backed_fields += 1
        if evidence_backed_fields == 0:
            raise _conflict(f"scene {scene.index} has no evidence-backed factual field")
