"""Best-effort online-reference enrichment for narration generation."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from military_video_gen.config.schema import ResearchConfig
from military_video_gen.services.llm_service import LLMService
from military_video_gen.utils.content_generators import generate_narrations_from_topic

from .models import ResearchRequest
from .service import (
    ReferenceMaterial,
    ResearchService,
    ResearchUnavailableError,
    build_research_service,
)


@dataclass(frozen=True)
class ResearchedNarrations:
    narrations: list[str]
    research_status: str
    queries: list[str]
    sources: list[dict]
    warnings: list[str]


NarrationGenerator = Callable[..., Awaitable[list[str]]]


def _reference_context(material: ReferenceMaterial) -> str:
    source_by_id = {source.id: source for source in material.sources}
    entries: list[str] = []
    for claim in material.safe_claims[:16]:
        quotes = " | ".join(
            f'原文：“{quote.quote}”'
            for quote in claim.evidence_quotes[:2]
        )
        source_links = ", ".join(
            str(source_by_id[source_id].url)
            for source_id in claim.source_ids
            if source_id in source_by_id
        )
        entries.append(f"- {claim.statement}\n  {quotes}\n  来源：{source_links}")
    return "\n".join(entries)


async def generate_researched_narrations(
    *,
    llm_service: LLMService,
    project_id: str,
    topic: str,
    n_scenes: int,
    min_words: int,
    max_words: int,
    research_config: ResearchConfig | None = None,
    research_service: ResearchService | None = None,
    narration_generator: NarrationGenerator = generate_narrations_from_topic,
    require_references: bool = False,
) -> ResearchedNarrations:
    if research_service is None:
        if research_config is None:
            raise ValueError("research_config is required")
        research_service = build_research_service(research_config, llm_service)

    request = ResearchRequest(
        project_id=project_id,
        topic=topic,
        narrations=[topic],
        asset_type="video",
        script_revision=0,
    )
    material: ReferenceMaterial | None = None
    queries: list[str] = []
    sources: list[dict] = []
    warnings: list[str] = []
    try:
        async with asyncio.timeout(
            getattr(research_service, "total_timeout_seconds", 120)
        ):
            material = await research_service.collect_reference_material(
                request,
                progress=lambda *_: None,
            )
        queries = material.queries
        sources = [source.model_dump(mode="json") for source in material.sources]
        warnings.extend(material.warnings)
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        warnings.append("reference_timeout")
    except ResearchUnavailableError as error:
        queries = error.queries
        sources = [source.model_dump(mode="json") for source in error.sources]
        warnings.append(error.warning)
    except Exception:
        warnings.append("reference_unavailable")

    context = _reference_context(material) if material is not None else ""
    has_references = bool(material and material.safe_claims and context.strip())

    if require_references and not has_references:
        warning = warnings[0] if warnings else "reference_extraction_empty"
        raise ResearchUnavailableError(
            warning,
            queries=queries,
            sources=material.sources if material is not None else [],
        )

    generator_kwargs = {
        "llm_service": llm_service,
        "topic": topic,
        "n_scenes": n_scenes,
        "min_words": min_words,
        "max_words": max_words,
    }
    if has_references:
        generator_kwargs["reference_context"] = context
    planning_budget = getattr(research_service, "planning_timeout_seconds", 120)
    generator_kwargs["planning_timeout_seconds"] = planning_budget
    generator_kwargs["writing_timeout_seconds"] = max(120, planning_budget)
    narrations = await narration_generator(**generator_kwargs)
    return ResearchedNarrations(
        narrations=narrations,
        research_status=(
            "partial_reference"
            if has_references and warnings
            else "reference_ready"
            if has_references
            else "reference_unavailable"
        ),
        queries=queries,
        sources=sources,
        warnings=warnings or ([] if has_references else ["reference_extraction_empty"]),
    )
