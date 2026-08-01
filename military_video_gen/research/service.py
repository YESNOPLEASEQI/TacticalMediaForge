"""Bounded web-reference enrichment for storyboard generation."""

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from military_video_gen.config.schema import ResearchConfig
from military_video_gen.services.llm_service import LLMService

from .claim_validator import ClaimValidator
from .crawlers.base import CrawlProvider
from .crawlers.crawl4ai import Crawl4AIProvider
from .evidence_extractor import EvidenceExtractor
from .freshness import compute_input_hash
from .models import (
    ClaimStatus,
    CrawledDocument,
    EvidenceClaim,
    FallbackLevel,
    FieldProvenance,
    GenericFallback,
    GroundedField,
    GroundedStoryboardScene,
    ResearchPhase,
    ResearchRequest,
    ResearchSnapshot,
    ResearchStatus,
    Source,
    SourceType,
    SubjectProfile,
    VerificationStatus,
    VisualFact,
)
from .providers.search import SearchProvider
from .providers.searxng import SearchUnavailableError, SearXNGProvider
from .query_planner import QueryPlanner
from .source_ranker import deduplicate_documents, score_claim_source
from .visual_fact_extractor import VisualFactExtractor
from .visual_planner import VisualPlanner

ProgressCallback = Callable[[ResearchPhase, int, int], None]

_NEWS_DOMAINS = (
    "163.com",
    "cctv.com",
    "gmw.cn",
    "news.cn",
    "people.com.cn",
    "qq.com",
    "sina.com.cn",
    "sohu.com",
    "xinhuanet.com",
)
_REFERENCE_DOMAINS = ("baike.baidu.com", "wikipedia.org")


def _matches_domain(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in domains)


class ResearchUnavailableError(RuntimeError):
    """Online-reference collection could not produce usable material."""

    def __init__(
        self,
        warning: str,
        *,
        queries: list[str] | None = None,
        sources: list[Source] | None = None,
    ) -> None:
        super().__init__(warning)
        self.warning = warning
        self.queries = queries or []
        self.sources = sources or []


def provider_failure_warning(error: Exception, default: str) -> str:
    """Map real provider failures to stable, non-secret UI warning codes."""
    status_code = getattr(error, "status_code", None)
    message = str(error).casefold()
    if status_code == 401:
        return "llm_authentication_failed"
    if status_code == 402 or "insufficient balance" in message:
        return "llm_insufficient_balance"
    if status_code == 404:
        return "llm_endpoint_or_model_not_found"
    if status_code == 429:
        return "llm_rate_limited"
    return default


@dataclass(frozen=True)
class ReferenceMaterial:
    """Reusable output of the strict search, crawl, and extraction stages."""

    queries: list[str]
    sources: list[Source]
    claims: list[EvidenceClaim]
    visual_facts: list[VisualFact]
    safe_claims: list[EvidenceClaim]
    safe_visual_facts: list[VisualFact]
    warnings: list[str]


def _source_type(url: str) -> SourceType:
    host = (urlsplit(url).hostname or "").casefold()
    if host.endswith(".mil"):
        return SourceType.OFFICIAL
    if host.endswith(".gov") or ".gov." in host:
        return SourceType.GOVERNMENT
    if host.endswith((".edu", ".ac.uk", ".ac.cn")):
        return SourceType.RESEARCH
    if host == "lockheedmartin.com" or host.endswith(".lockheedmartin.com"):
        return SourceType.MANUFACTURER
    if _matches_domain(host, _NEWS_DOMAINS):
        return SourceType.NEWS
    if _matches_domain(host, _REFERENCE_DOMAINS):
        return SourceType.REFERENCE
    return SourceType.OTHER


class ResearchService:
    def __init__(
        self,
        *,
        search_provider: SearchProvider,
        crawl_provider: CrawlProvider,
        query_planner,
        evidence_extractor,
        claim_validator,
        visual_fact_extractor,
        visual_planner,
        minimum_visual_confidence: float,
        total_timeout_seconds: float = 120,
        extraction_timeout_seconds: float = 45,
        planning_timeout_seconds: float = 30,
        max_results_per_query: int = 5,
        max_queries: int = 5,
        max_pages: int = 8,
        max_pages_per_domain: int = 2,
        max_rounds: int = 1,
    ) -> None:
        self.search_provider = search_provider
        self.crawl_provider = crawl_provider
        self.query_planner = query_planner
        self.evidence_extractor = evidence_extractor
        self.claim_validator = claim_validator
        self.visual_fact_extractor = visual_fact_extractor
        self.visual_planner = visual_planner
        self.minimum_visual_confidence = minimum_visual_confidence
        self.total_timeout_seconds = total_timeout_seconds
        self.extraction_timeout_seconds = extraction_timeout_seconds
        self.planning_timeout_seconds = planning_timeout_seconds
        self.max_results_per_query = max_results_per_query
        self.max_queries = max_queries
        self.max_pages = max_pages
        self.max_pages_per_domain = max_pages_per_domain
        self.max_rounds = max_rounds

    async def run(
        self,
        request: ResearchRequest,
        *,
        progress: ProgressCallback,
    ) -> ResearchSnapshot:
        try:
            async with asyncio.timeout(self.total_timeout_seconds):
                material = await self.collect_reference_material(request, progress=progress)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            material = self._empty_material("reference_timeout")
        except ResearchUnavailableError as error:
            material = ReferenceMaterial(
                queries=error.queries,
                sources=error.sources,
                claims=[],
                visual_facts=[],
                safe_claims=[],
                safe_visual_facts=[],
                warnings=[error.warning],
            )
        except Exception:
            material = self._empty_material("reference_unavailable")

        subject_profiles = self._build_subject_profiles(material.safe_visual_facts)
        references_applied = bool(material.safe_claims)
        progress(ResearchPhase.PLANNING_STORYBOARD, 0, 1)
        try:
            subject_profiles, scenes = await asyncio.wait_for(
                self.visual_planner.plan(
                    request.narrations,
                    subject_profiles,
                    material.safe_visual_facts,
                    request.asset_type,
                    material.safe_claims,
                ),
                timeout=self.planning_timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            material = self._with_warning(material, "storyboard_planning_timeout")
            references_applied = False
            subject_profiles, scenes = await self._ordinary_or_local_plan(request, material)
        except Exception:
            material = self._with_warning(material, "storyboard_planning_unavailable")
            references_applied = False
            subject_profiles, scenes = await self._ordinary_or_local_plan(request, material)
        fallback_scene_count = sum("scene_prompt_fallback" in scene.warnings for scene in scenes)
        if fallback_scene_count == len(scenes) and scenes:
            references_applied = False
            material = self._with_warning(material, "storyboard_prompt_fallback")
        elif fallback_scene_count:
            material = self._with_warning(
                material,
                "partial_storyboard_prompt_fallback",
            )
        safe_claims_by_id = {claim.id: claim for claim in material.safe_claims}
        self._normalize_generated_scenes(
            request,
            scenes,
            safe_claims_by_id,
            safe_visual_fact_ids={fact.id for fact in material.safe_visual_facts},
        )
        progress(ResearchPhase.PLANNING_STORYBOARD, 1, 1)

        if not material.safe_claims or not references_applied:
            research_status = ResearchStatus.REFERENCE_UNAVAILABLE
        elif material.warnings:
            research_status = ResearchStatus.PARTIAL_REFERENCE
        else:
            research_status = ResearchStatus.REFERENCE_READY
        supported_scenes = [
            scene
            for scene in scenes
            if scene.verification_status
            in {
                VerificationStatus.VERIFIED,
                VerificationStatus.LOW_CONFIDENCE_VERIFIED,
                VerificationStatus.PARTIAL,
            }
        ]
        if len(supported_scenes) != len(scenes) or not scenes:
            verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
        elif material.warnings:
            verification_status = VerificationStatus.PARTIAL
        elif any(
            scene.verification_status == VerificationStatus.LOW_CONFIDENCE_VERIFIED
            for scene in supported_scenes
        ):
            verification_status = VerificationStatus.LOW_CONFIDENCE_VERIFIED
        else:
            verification_status = VerificationStatus.VERIFIED
        snapshot = self._snapshot(
            request,
            queries=material.queries,
            sources=material.sources,
            claims=material.claims,
            subject_profiles=subject_profiles,
            visual_facts=material.visual_facts,
            storyboard_plan=scenes,
            research_status=research_status,
            verification_status=verification_status,
            warnings=material.warnings,
        )
        progress(ResearchPhase.RENDERING_PROMPTS, 0, len(snapshot.storyboard_plan))
        for index, scene in enumerate(snapshot.storyboard_plan, start=1):
            progress(ResearchPhase.RENDERING_PROMPTS, index, len(snapshot.storyboard_plan))
        return snapshot

    async def _ordinary_or_local_plan(
        self,
        request: ResearchRequest,
        material: ReferenceMaterial,
    ) -> tuple[list[SubjectProfile], list[GroundedStoryboardScene]]:
        """Generate from narrations after research planning fails.

        This is deliberately a fresh ordinary-generation call. The deterministic
        local plan is only the final availability fallback, not the first response
        to a slow reference prompt.
        """
        del material
        try:
            ordinary_plan = getattr(self.visual_planner, "plan_ordinary", None)
            if ordinary_plan is not None:
                try:
                    ordinary_call = ordinary_plan(
                        request.narrations,
                        request.asset_type,
                        topic=request.topic,
                    )
                except TypeError:
                    ordinary_call = ordinary_plan(
                        request.narrations,
                        request.asset_type,
                    )
                return await asyncio.wait_for(
                    ordinary_call,
                    timeout=self.planning_timeout_seconds,
                )
            return await asyncio.wait_for(
                self.visual_planner.plan(
                    request.narrations,
                    [],
                    [],
                    request.asset_type,
                    [],
                ),
                timeout=self.planning_timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            try:
                return self.visual_planner.fallback_plan(
                    request.narrations,
                    request.asset_type,
                    topic=request.topic,
                )
            except TypeError:
                # Preserve compatibility with lightweight third-party/test
                # planners that still expose the earlier two-argument hook.
                return self.visual_planner.fallback_plan(
                    request.narrations,
                    request.asset_type,
                )

    @staticmethod
    def _empty_material(warning: str) -> ReferenceMaterial:
        return ReferenceMaterial([], [], [], [], [], [], [warning])

    @staticmethod
    def _with_warning(material: ReferenceMaterial, warning: str) -> ReferenceMaterial:
        return ReferenceMaterial(
            queries=material.queries,
            sources=material.sources,
            claims=material.claims,
            visual_facts=material.visual_facts,
            safe_claims=material.safe_claims,
            safe_visual_facts=material.safe_visual_facts,
            warnings=list(dict.fromkeys([*material.warnings, warning])),
        )

    async def collect_reference_material(
        self,
        request: ResearchRequest,
        *,
        progress: ProgressCallback,
    ) -> ReferenceMaterial:
        progress(ResearchPhase.PLANNING_QUERIES, 0, 1)
        try:
            planned_queries = await asyncio.wait_for(
                self.query_planner.plan(request.topic, request.narrations),
                timeout=self.planning_timeout_seconds,
            )
            initial_limit = max(
                1,
                self.max_queries - 1 if self.max_rounds > 1 else self.max_queries,
            )
            queries = planned_queries[:initial_limit]
        except TimeoutError as error:
            raise ResearchUnavailableError("reference_timeout") from error
        except Exception as error:
            raise ResearchUnavailableError(
                provider_failure_warning(error, "search_unavailable")
            ) from error
        progress(ResearchPhase.PLANNING_QUERIES, 1, 1)

        candidates = []
        search_failures = 0
        progress(ResearchPhase.SEARCHING, 0, len(queries))

        async def search(query: str):
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    results = await self.search_provider.search(query)
                    if results:
                        return results
                    last_error = SearchUnavailableError("search returned no results")
                except (SearchUnavailableError, OSError, TimeoutError) as error:
                    last_error = error
                if attempt < 2:
                    await asyncio.sleep(0.25 * (attempt + 1))
            raise SearchUnavailableError(
                f"search failed after retries for query: {query}"
            ) from last_error

        for index, query in enumerate(queries, start=1):
            try:
                results = await search(query)
            except asyncio.CancelledError:
                raise
            except Exception:
                search_failures += 1
            else:
                candidates.extend(results[: self.max_results_per_query])
            progress(ResearchPhase.SEARCHING, index, len(queries))

        if self.max_rounds > 1 and len(queries) < self.max_queries:
            manufacturer_domains = list(
                dict.fromkeys(
                    (urlsplit(str(candidate.url)).hostname or "").casefold()
                    for candidate in candidates
                    if _source_type(str(candidate.url)) is SourceType.MANUFACTURER
                )
            )
            identifiers = re.findall(
                r"(?<![a-z0-9])[a-z]{1,8}\s*-?\s*\d[a-z0-9-]*(?![a-z0-9])",
                request.topic.casefold(),
            )
            if manufacturer_domains and identifiers:
                identifier = re.sub(r"\s+", "", identifiers[0]).upper()
                domain = manufacturer_domains[0].removeprefix("www.")
                followup_query = f"{identifier} site:{domain} history first flight design"
                queries.append(followup_query)
                try:
                    followup_results = await search(followup_query)
                except SearchUnavailableError:
                    search_failures += 1
                else:
                    candidates.extend(followup_results[: self.max_results_per_query])
                progress(ResearchPhase.SEARCHING, len(queries), len(queries))
        candidates = self._limit_candidates(
            candidates,
            topic=request.topic,
            narrations=request.narrations,
        )
        if not candidates:
            raise ResearchUnavailableError("search_unavailable", queries=queries)
        progress(ResearchPhase.CRAWLING, 0, len(candidates))
        try:
            documents = await self.crawl_provider.crawl_many(
                candidates,
                force_refresh=request.force_refresh,
            )
        except Exception as error:
            raise ResearchUnavailableError("crawl_unavailable", queries=queries) from error
        progress(ResearchPhase.CRAWLING, len(candidates), len(candidates))
        usable = [document for document in documents if not document.error and document.markdown][
            : self.max_pages
        ]
        crawl_failures = len(documents) - len(usable)
        if not usable:
            raise ResearchUnavailableError("all_crawls_failed", queries=queries)

        usable, groups = deduplicate_documents(usable)
        sources = self._sources_from_documents(usable, groups)

        progress(ResearchPhase.EXTRACTING_EVIDENCE, 0, 1)
        try:
            claims = await asyncio.wait_for(
                self.evidence_extractor.extract(usable, sources),
                timeout=self.extraction_timeout_seconds,
            )
        except TimeoutError as error:
            raise ResearchUnavailableError(
                "reference_timeout", queries=queries, sources=sources
            ) from error
        except Exception as error:
            raise ResearchUnavailableError(
                provider_failure_warning(error, "reference_extraction_empty"),
                queries=queries,
                sources=sources,
            ) from error
        progress(ResearchPhase.EXTRACTING_EVIDENCE, 1, 1)
        cleaned_claims = self.claim_validator.clean(claims, sources)
        claims = self._filter_relevant_claims(
            cleaned_claims,
            sources,
            topic=request.topic,
            narrations=request.narrations,
        )
        if not claims:
            raise ResearchUnavailableError(
                ("reference_relevance_empty" if cleaned_claims else "reference_extraction_empty"),
                queries=queries,
                sources=sources,
            )
        relevant_source_ids = {source_id for claim in claims for source_id in claim.source_ids}
        sources = [source for source in sources if source.id in relevant_source_ids]

        progress(ResearchPhase.EXTRACTING_VISUAL_FACTS, 0, 1)
        try:
            visual_facts = await asyncio.wait_for(
                self.visual_fact_extractor.extract(claims),
                timeout=min(
                    self.extraction_timeout_seconds,
                    self.planning_timeout_seconds / 2,
                ),
            )
        except Exception:
            visual_facts = []
        progress(ResearchPhase.EXTRACTING_VISUAL_FACTS, 1, 1)
        safe_claims = [
            claim
            for claim in claims
            if not claim.conflicts
            and claim.status in {ClaimStatus.VERIFIED, ClaimStatus.LOW_CONFIDENCE_VERIFIED}
        ]
        safe_claim_ids = {claim.id for claim in safe_claims}
        safe_visual_facts = [
            fact
            for fact in visual_facts
            if all(claim_id in safe_claim_ids for claim_id in fact.claim_ids)
        ]
        research_warnings = []
        if search_failures:
            research_warnings.append("partial_search_failure")
        if crawl_failures:
            research_warnings.append("partial_crawl_failure")
        if len(claims) < len(cleaned_claims):
            research_warnings.append("partial_reference_mismatch")
        if not safe_claims:
            raise ResearchUnavailableError(
                "reference_extraction_empty", queries=queries, sources=sources
            )

        return ReferenceMaterial(
            queries=queries,
            sources=sources,
            claims=claims,
            visual_facts=visual_facts,
            safe_claims=safe_claims,
            safe_visual_facts=safe_visual_facts,
            warnings=research_warnings,
        )

    @staticmethod
    def _relevance_tokens(value: str) -> set[str]:
        normalized = value.casefold()
        words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized))
        runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
        bigrams = {run[index : index + 2] for run in runs for index in range(max(0, len(run) - 1))}
        return words | bigrams

    def _limit_candidates(
        self,
        candidates,
        *,
        topic: str,
        narrations: list[str],
    ):
        limited = []
        seen: set[str] = set()
        domain_counts: dict[str, int] = {}
        topic_tokens = self._relevance_tokens(topic)
        narration_tokens = self._relevance_tokens(" ".join(narrations)) - topic_tokens
        anti_bot_hosts = ("toutiao.com", "csdn.net", "zhihu.com")
        profile_terms = ("声优", "配音", "男演员", "女演员", "血型", "生日", "明星", "艺人")

        def rank(candidate) -> tuple[int, int, int]:
            url = str(candidate.url)
            domain = (urlsplit(url).hostname or "").casefold()
            text = f"{candidate.title} {candidate.snippet}"
            text_tokens = self._relevance_tokens(text)
            topic_overlap = len(topic_tokens & text_tokens)
            narration_overlap = len(narration_tokens & text_tokens)
            authority = {
                SourceType.OFFICIAL: 3,
                SourceType.GOVERNMENT: 3,
                SourceType.RESEARCH: 2,
                SourceType.MANUFACTURER: 2,
            }.get(_source_type(url), 0)
            history_page = (
                20
                if authority and ("/history/" in url.casefold() or "history" in text.casefold())
                else 0
            )
            anti_bot = -20 if domain.endswith(anti_bot_hosts) else 0
            entity_mismatch = (
                -40
                if any(term in text.casefold() for term in profile_terms)
                and not any(term in " ".join(narrations).casefold() for term in profile_terms)
                else 0
            )
            return (
                1 if authority else 0,
                narration_overlap * 12
                + topic_overlap * 4
                + authority
                + history_page
                + anti_bot
                + entity_mismatch,
                len(text),
            )

        for candidate in sorted(candidates, key=rank, reverse=True):
            url = str(candidate.url).rstrip("/")
            domain = (urlsplit(url).hostname or "").casefold()
            if url in seen or domain_counts.get(domain, 0) >= self.max_pages_per_domain:
                continue
            seen.add(url)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            limited.append(candidate)
            if len(limited) >= self.max_pages:
                break
        return limited

    def _filter_relevant_claims(
        self,
        claims: list[EvidenceClaim],
        sources: list[Source],
        *,
        topic: str,
        narrations: list[str],
    ) -> list[EvidenceClaim]:
        """Remove same-name entity claims that cannot support the supplied script."""
        topic_tokens = self._relevance_tokens(topic)
        narration_text = " ".join(narrations)
        narration_tokens = self._relevance_tokens(narration_text) - topic_tokens
        topic_identifiers = set(
            re.findall(
                r"(?<![a-z0-9])[a-z]{1,8}\s*-?\s*\d[a-z0-9-]*(?![a-z0-9])",
                topic.casefold(),
            )
        )
        topic_identifiers = {re.sub(r"\s+", "", value) for value in topic_identifiers}
        source_by_id = {source.id: source for source in sources}
        profile_terms = (
            "声优",
            "配音",
            "演员",
            "血型",
            "生日",
            "星座",
            "艺人",
            "voice actor",
            "birthday",
            "blood type",
        )
        military_terms = (
            "军事",
            "武器",
            "火炮",
            "炮管",
            "炮弹",
            "弹丸",
            "火药",
            "膛线",
            "雷达",
            "导弹",
            "飞机",
            "舰艇",
            "航母",
            "潜艇",
            "坦克",
            "artillery",
            "cannon",
            "weapon",
            "barrel",
            "projectile",
            "propellant",
            "radar",
            "missile",
            "aircraft",
        )

        relevant = []
        for claim in claims:
            claim_text = " ".join(
                [claim.statement, claim.subject, claim.predicate, claim.value]
            ).casefold()
            source_text = " ".join(
                source_by_id[source_id].title
                for source_id in claim.source_ids
                if source_id in source_by_id
            ).casefold()
            combined = f"{claim_text} {source_text}"
            if any(term in combined for term in profile_terms) and not any(
                term in narration_text.casefold() for term in profile_terms
            ):
                continue
            semantic_overlap = narration_tokens & self._relevance_tokens(combined)
            topic_overlap = topic_tokens & self._relevance_tokens(combined)
            military_context = any(term in combined for term in military_terms)
            normalized_combined = re.sub(r"\s+", "", combined)
            trusted_identifier_match = (
                bool(topic_identifiers)
                and any(identifier in normalized_combined for identifier in topic_identifiers)
                and any(
                    source_by_id[source_id].source_type
                    in {
                        SourceType.OFFICIAL,
                        SourceType.GOVERNMENT,
                        SourceType.RESEARCH,
                        SourceType.MANUFACTURER,
                    }
                    for source_id in claim.source_ids
                    if source_id in source_by_id
                )
            )
            if semantic_overlap or (topic_overlap and military_context) or trusted_identifier_match:
                relevant.append(claim)
        return relevant

    @staticmethod
    def _claim_supports_narration_numbers(
        narration: str,
        claim: EvidenceClaim,
    ) -> bool:
        """Reject claim links that contradict explicit narration numbers/years."""
        narration_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", narration))
        if not narration_numbers:
            return True
        claim_text = " ".join([claim.statement, claim.subject, claim.predicate, claim.value])
        claim_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", claim_text))
        return narration_numbers.issubset(claim_numbers)

    @staticmethod
    def _normalize_generated_scenes(
        request: ResearchRequest,
        scenes: list[GroundedStoryboardScene],
        safe_claims_by_id: dict[str, EvidenceClaim],
        *,
        safe_visual_fact_ids: set[str] | None = None,
    ) -> None:
        if len(scenes) != len(request.narrations):
            raise ValueError("storyboard scene count does not match narration count")
        for index, (scene, narration) in enumerate(
            zip(scenes, request.narrations, strict=True),
            start=1,
        ):
            scene.scene_index = index
            scene.narration = narration
            scene.asset_type = request.asset_type
            scene.generic_fallback = None
            scene.claim_ids = [
                claim_id
                for claim_id in scene.claim_ids
                if claim_id in safe_claims_by_id
                and ResearchService._claim_supports_narration_numbers(
                    narration,
                    safe_claims_by_id[claim_id],
                )
            ]
            allowed_visual_fact_ids = safe_visual_fact_ids or set()
            scene.visual_fact_ids = [
                visual_fact_id
                for visual_fact_id in scene.visual_fact_ids
                if visual_fact_id in allowed_visual_fact_ids
            ]
            if scene.claim_ids:
                # Evidence records provenance; it is not an allow-list for
                # cinematography. Preserve the complete LTX prompt and classify
                # factual identity separately from creative staging.
                source_subjects = list(
                    dict.fromkeys(
                        safe_claims_by_id[claim_id].subject.strip()
                        for claim_id in scene.claim_ids
                        if safe_claims_by_id[claim_id].subject.strip()
                    )
                )
                subject = " / ".join(source_subjects)
                if not subject or re.search(
                    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]",
                    subject,
                ):
                    subject = VisualPlanner._fallback_subject_anchor(
                        " ".join(source_subjects),
                        [narration],
                    )
                scene.subject = GroundedField(
                    value=subject,
                    provenance=FieldProvenance(
                        claim_ids=list(scene.claim_ids),
                        creative=False,
                    ),
                )
                creative_fields = {
                    "environment": "Creative environment described in the media prompt",
                    "opening_state": "Creative opening state described in the media prompt",
                    "action": "Creative visible action described in the media prompt",
                    "camera": "Creative camera behavior described in the media prompt",
                    "composition": "Creative composition described in the media prompt",
                    "lighting": "Creative lighting described in the media prompt",
                    "ending_frame": "Creative ending state described in the media prompt",
                }
                for field_name, fallback_value in creative_fields.items():
                    current = getattr(scene, field_name)
                    value = current.value.strip() or fallback_value
                    setattr(
                        scene,
                        field_name,
                        GroundedField(
                            value=value,
                            creative=True,
                            generic_safe=True,
                        ),
                    )
                scene.media_prompt = scene.media_prompt.strip()
                scene.visual_description = scene.media_prompt
                scene.fallback_level = FallbackLevel.VERIFIED_GENERIC
                scene.verification_status = (
                    VerificationStatus.LOW_CONFIDENCE_VERIFIED
                    if any(
                        safe_claims_by_id[claim_id].status == ClaimStatus.LOW_CONFIDENCE_VERIFIED
                        for claim_id in scene.claim_ids
                    )
                    else VerificationStatus.VERIFIED
                )
            else:
                scene.fallback_level = FallbackLevel.INSUFFICIENT_EVIDENCE
                scene.verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
                if "scene_has_no_verified_claims" not in scene.warnings:
                    scene.warnings.append("scene_has_no_verified_claims")

    def _sources_from_documents(
        self,
        documents: list[CrawledDocument],
        groups: dict[str, str],
    ) -> list[Source]:
        sources: list[Source] = []
        for index, document in enumerate(documents, start=1):
            url = str(document.url).rstrip("/")
            source_type = _source_type(url)
            source = Source(
                id=f"source-{index}",
                url=document.url,
                canonical_url=document.canonical_url,
                title=document.title or url,
                source_type=source_type,
                published_at=document.published_at,
                fetched_at=document.fetched_at,
                content_hash=document.content_hash,
                independence_group=groups.get(url),
            )
            source.score = score_claim_source(source, claim_kind="public_fact")
            sources.append(source)
        return sources

    def _build_subject_profiles(self, visual_facts) -> list[SubjectProfile]:
        subject_ids = sorted({fact.subject_id or "subject-1" for fact in visual_facts})
        return [
            SubjectProfile(
                id=subject_id,
                canonical_name="verified military subject",
                category="military subject",
                confirmed_visual_traits=[
                    fact.allowed_detail
                    for fact in visual_facts
                    if (fact.subject_id or "subject-1") == subject_id
                ],
                generic_fallback=GenericFallback(category="generic military subject"),
            )
            for subject_id in subject_ids
        ]

    def _snapshot(
        self,
        request: ResearchRequest,
        *,
        queries: list[str] | None = None,
        sources: list[Source] | None = None,
        claims=None,
        subject_profiles=None,
        visual_facts=None,
        storyboard_plan=None,
        research_status: ResearchStatus,
        verification_status: VerificationStatus,
        warnings: list[str] | None = None,
    ) -> ResearchSnapshot:
        return ResearchSnapshot(
            topic=request.topic,
            input_hash=compute_input_hash(
                topic=request.topic,
                narrations=request.narrations,
                asset_type=request.asset_type,
                mode=request.mode,
            ),
            script_revision=request.script_revision,
            researched_at=datetime.now(UTC),
            research_status=research_status,
            verification_status=verification_status,
            queries=queries or [],
            sources=sources or [],
            claims=claims or [],
            subject_profiles=subject_profiles or [],
            visual_facts=visual_facts or [],
            storyboard_plan=storyboard_plan or [],
            warnings=warnings or [],
        )


def build_research_service(config: ResearchConfig, llm: LLMService) -> ResearchService:
    """Construct the production service without reading token values into config."""
    search = SearXNGProvider(
        config.search.base_url,
        timeout_seconds=config.search.timeout_seconds,
        engines=config.search.engines,
    )
    crawl = Crawl4AIProvider(config.crawl)
    return ResearchService(
        search_provider=search,
        crawl_provider=crawl,
        query_planner=QueryPlanner(llm),
        evidence_extractor=EvidenceExtractor(
            llm,
            model=config.verification.structured_model,
        ),
        claim_validator=ClaimValidator(
            minimum_confidence=config.verification.minimum_verified_claim_confidence,
            minimum_low_confidence=(config.verification.minimum_low_confidence_claim_confidence),
            minimum_discovery_confidence=(config.verification.minimum_discovery_claim_confidence),
        ),
        visual_fact_extractor=VisualFactExtractor(
            llm,
            minimum_confidence=config.verification.minimum_visual_fact_confidence,
            model=config.verification.structured_model,
        ),
        visual_planner=VisualPlanner(
            llm,
            model=config.verification.structured_model,
            scene_timeout_seconds=config.verification.planning_timeout_seconds,
        ),
        minimum_visual_confidence=config.verification.minimum_visual_fact_confidence,
        total_timeout_seconds=config.verification.total_timeout_seconds,
        extraction_timeout_seconds=(config.verification.extraction_timeout_seconds),
        planning_timeout_seconds=config.verification.planning_timeout_seconds,
        max_results_per_query=config.search.max_results_per_query,
        max_queries=config.search.max_queries,
        max_pages=config.search.max_pages,
        max_pages_per_domain=config.search.max_pages_per_domain,
        max_rounds=config.search.max_rounds,
    )
