"""Typed evidence, provenance, and grounded storyboard contracts."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from military_video_gen.utils.safety import enforce_safe_generation_text


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    LOW_CONFIDENCE_VERIFIED = "low_confidence_verified"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIED = "unverified"


class ResearchStatus(str, Enum):
    RESEARCHING = "researching"
    REFERENCE_READY = "reference_ready"
    PARTIAL_REFERENCE = "partial_reference"
    REFERENCE_UNAVAILABLE = "reference_unavailable"
    QUICK = "quick"


class ClaimStatus(str, Enum):
    VERIFIED = "verified"
    LOW_CONFIDENCE_VERIFIED = "low_confidence_verified"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONFLICTED = "conflicted"
    UNSUPPORTED = "unsupported"


class FallbackLevel(str, Enum):
    VERIFIED_SPECIFIC = "verified_specific"
    VERIFIED_GENERIC = "verified_generic"
    GENERIC_SAFE = "generic_safe"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIED = "unverified"


class SourceType(str, Enum):
    OFFICIAL = "official"
    GOVERNMENT = "government"
    MANUFACTURER = "manufacturer"
    RESEARCH = "research"
    NEWS = "news"
    REFERENCE = "reference"
    OTHER = "other"


class ResearchPhase(str, Enum):
    PLANNING_QUERIES = "planning_queries"
    SEARCHING = "searching"
    CRAWLING = "crawling"
    EXTRACTING_EVIDENCE = "extracting_evidence"
    EXTRACTING_VISUAL_FACTS = "extracting_visual_facts"
    PLANNING_STORYBOARD = "planning_storyboard"
    RENDERING_PROMPTS = "rendering_prompts"


class SearchCandidate(BaseModel):
    url: HttpUrl
    title: str
    snippet: str = ""
    query: str = ""


class CrawledDocument(BaseModel):
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str = ""
    markdown: str
    links: list[HttpUrl] = Field(default_factory=list)
    published_at: datetime | None = None
    content_type: str = "text/html"
    content_hash: str
    fetched_at: datetime
    truncated: bool = False
    error: str | None = None


class Source(BaseModel):
    id: str
    url: HttpUrl
    canonical_url: HttpUrl | None = None
    title: str
    publisher: str | None = None
    source_type: SourceType = SourceType.OTHER
    published_at: datetime | None = None
    fetched_at: datetime
    content_hash: str
    independence_group: str | None = None
    score: float = Field(default=0, ge=0, le=1)
    conflict_notes: list[str] = Field(default_factory=list)


class EvidenceQuote(BaseModel):
    source_id: str
    quote: str = Field(min_length=1)
    location: str | None = None


class EvidenceClaim(BaseModel):
    id: str
    statement: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    evidence_quotes: list[EvidenceQuote] = Field(min_length=1)
    status: ClaimStatus
    confidence: float = Field(ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    valid_at: datetime | None = None


class GenericFallback(BaseModel):
    category: str
    identifying_markings: bool = False


class SubjectProfile(BaseModel):
    id: str
    canonical_name: str
    category: str
    variant: str | None = None
    confirmed_visual_traits: list[str] = Field(default_factory=list)
    confirmed_contexts: list[str] = Field(default_factory=list)
    details_to_avoid: list[str] = Field(default_factory=list)
    generic_fallback: GenericFallback


class VisualFact(BaseModel):
    id: str
    subject_id: str | None = None
    fact: str
    claim_ids: list[str] = Field(min_length=1)
    allowed_detail: str
    forbidden_inference: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class FieldProvenance(BaseModel):
    claim_ids: list[str] = Field(default_factory=list)
    visual_fact_ids: list[str] = Field(default_factory=list)
    creative: bool = False


class GroundedField(BaseModel):
    value: str = ""
    provenance: FieldProvenance | None = None
    creative: bool = False
    generic_safe: bool = False


class GroundedStoryboardScene(BaseModel):
    scene_index: int = Field(ge=1)
    narration: str
    visual_description: str = ""
    media_prompt: str = ""
    estimated_duration: float = Field(default=0, ge=0)
    asset_type: Literal["image", "video"] = "video"
    subject_id: str | None = None
    subject: GroundedField
    environment: GroundedField
    opening_state: GroundedField
    action: GroundedField
    camera: GroundedField
    composition: GroundedField
    lighting: GroundedField
    ending_frame: GroundedField
    claim_ids: list[str] = Field(default_factory=list)
    visual_fact_ids: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    fallback_level: FallbackLevel
    verification_status: VerificationStatus
    warnings: list[str] = Field(default_factory=list)
    generic_fallback: "GroundedStoryboardScene | None" = None

    @property
    def field_provenance(self) -> dict[str, FieldProvenance]:
        result: dict[str, FieldProvenance] = {}
        for name in (
            "subject",
            "environment",
            "opening_state",
            "action",
            "camera",
            "composition",
            "lighting",
            "ending_frame",
        ):
            field = getattr(self, name)
            if field.provenance is not None:
                result[name] = field.provenance
            elif field.creative:
                result[name] = FieldProvenance(creative=True)
        return result


class ResearchRequest(BaseModel):
    project_id: str
    topic: str = Field(min_length=1)
    narrations: list[str] = Field(min_length=1)
    asset_type: Literal["image", "video"] = "video"
    mode: Literal["verified"] = "verified"
    script_revision: int = Field(default=0, ge=0)
    force_refresh: bool = False
    parent_job_id: str | None = None

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("topic must not be blank")
        return enforce_safe_generation_text(value, field_name="topic")

    @field_validator("narrations", mode="before")
    @classmethod
    def validate_narration_container(cls, value):
        if not isinstance(value, list):
            raise ValueError("narrations must be a list")
        return value

    @field_validator("narrations")
    @classmethod
    def validate_narrations(cls, value: list[str]) -> list[str]:
        cleaned = []
        for index, narration in enumerate(value):
            narration = narration.strip()
            if not narration:
                raise ValueError(f"narrations[{index}] must not be blank")
            cleaned.append(
                enforce_safe_generation_text(
                    narration,
                    field_name=f"narrations[{index}]",
                )
            )
        return cleaned


class ResearchSnapshot(BaseModel):
    schema_version: int = 1
    topic: str
    mode: Literal["verified"] = "verified"
    input_hash: str
    script_revision: int = Field(ge=0)
    researched_at: datetime
    research_status: ResearchStatus
    verification_status: VerificationStatus
    queries: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    claims: list[EvidenceClaim] = Field(default_factory=list)
    subject_profiles: list[SubjectProfile] = Field(default_factory=list)
    visual_facts: list[VisualFact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    storyboard_plan: list[GroundedStoryboardScene] = Field(default_factory=list)
