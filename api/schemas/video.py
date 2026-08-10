"""
Video generation API schemas
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from api.schemas.base import validate_reference_audio_path
from military_video_gen.prompts.legacy_contract import (
    contains_legacy_prompt,
    duplicate_prompt_groups,
)
from military_video_gen.research.models import (
    FallbackLevel,
    FieldProvenance,
    VerificationStatus,
)
from military_video_gen.utils.safety import enforce_safe_generation_text

_UNANCHORED_STORYBOARD_PHRASES = (
    "credible military technology subject",
    "one clearly readable mechanical or human action",
    "functional surfaces, moving parts, and material detail",
    "the subject interacting with its surroundings",
    "settles on a clear operational state",
)


class ConfirmedStoryboardScene(BaseModel):
    """A user-reviewed scene that can bypass LLM storyboard planning."""

    index: int = Field(..., ge=0)
    narration: str = Field(..., min_length=1)
    visual_description: str = ""
    media_prompt: str = ""
    estimated_duration: float = Field(0, ge=0)
    asset_type: Literal["image", "video"] = "video"
    research_job_id: Optional[str] = None
    subject_id: Optional[str] = None
    claim_ids: List[str] = Field(default_factory=list)
    visual_fact_ids: List[str] = Field(default_factory=list)
    field_provenance: Dict[str, FieldProvenance] = Field(default_factory=dict)
    fallback_level: FallbackLevel = FallbackLevel.UNVERIFIED
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    negative_constraints: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    reference_asset_ids: List[str] = Field(default_factory=list, max_length=4)

    @field_validator("reference_asset_ids")
    @classmethod
    def validate_reference_asset_ids(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("reference_asset_ids must not contain duplicates")
        if any(not item.strip() for item in value):
            raise ValueError("reference_asset_ids must contain non-empty IDs")
        return value

    @field_validator("narration", "visual_description", "media_prompt")
    @classmethod
    def validate_safe_scene_text(cls, value: str, info) -> str:
        if info.field_name == "narration" and not value.strip():
            raise ValueError("narration must not be blank")
        if value.strip():
            enforce_safe_generation_text(value, field_name=info.field_name)
        return value

    @field_validator("media_prompt")
    @classmethod
    def validate_english_media_prompt(cls, value: str) -> str:
        if any(
            "\u3400" <= character <= "\u4dbf"
            or "\u4e00" <= character <= "\u9fff"
            or "\uf900" <= character <= "\ufaff"
            for character in value
        ):
            raise ValueError("media_prompt must contain English text only")
        return value

    @model_validator(mode="after")
    def validate_effective_prompt_language(self):
        effective_prompt = self.media_prompt or self.visual_description
        if any(
            "\u3400" <= character <= "\u4dbf"
            or "\u4e00" <= character <= "\u9fff"
            or "\uf900" <= character <= "\ufaff"
            for character in effective_prompt
        ):
            raise ValueError("effective storyboard prompt must contain English text only")
        normalized = " ".join(effective_prompt.casefold().split())
        if any(phrase in normalized for phrase in _UNANCHORED_STORYBOARD_PHRASES):
            raise ValueError(
                "effective storyboard prompt must name the scene's concrete subject"
            )
        if contains_legacy_prompt(effective_prompt):
            raise ValueError(
                "effective storyboard prompt uses a retired prompt contract; "
                "regenerate the storyboard"
            )
        return self


class VideoGenerateRequest(BaseModel):
    """Video generation request"""
    
    # === Input ===
    text: str = Field(..., description="Source text for video generation")

    session_id: Optional[str] = Field(
        None,
        description="Existing history session being continued, when applicable",
    )
    confirmed_storyboard: Optional[List[ConfirmedStoryboardScene]] = Field(
        None,
        description="User-reviewed scenes. When present, narration and media prompts are reused exactly.",
    )
    verification_mode: Literal["verified", "unverified"] = "unverified"
    research_topic: Optional[str] = None
    script_revision: Optional[int] = Field(default=None, ge=0)
    workflow_revision: Optional[int] = Field(
        default=None,
        ge=0,
        description="Client draft revision used to bind a video job to the exact storyboard/config submitted.",
    )
    reference_mode: Literal["standard", "h3"] = "standard"
    
    # === Processing Mode ===
    mode: Literal["generate", "fixed"] = Field(
        "generate",
        description="Processing mode: 'generate' (AI generates narrations) or 'fixed' (use text as-is)"
    )
    
    # === Optional Title ===
    title: Optional[str] = Field(None, description="Video title (auto-generated if not provided)")
    
    # === Basic Config ===
    n_scenes: Optional[int] = Field(5, ge=1, le=20, description="Number of scenes (only used in 'generate' mode, ignored in 'fixed' mode)")
    
    # === TTS Parameters ===
    tts_workflow: Optional[str] = Field(
        None, 
        description="TTS workflow key (e.g., 'runninghub/tts_edge.json'). If not specified, uses default workflow from config."
    )
    ref_audio: Optional[str] = Field(
        None, 
        description="Reference audio path for voice cloning (optional)"
    )
    voice_id: Optional[str] = Field(
        None, 
        description="(Deprecated) TTS voice ID for legacy compatibility"
    )
    
    # === LLM Parameters ===
    min_narration_words: int = Field(5, ge=1, le=100, description="Min narration words")
    max_narration_words: int = Field(20, ge=1, le=200, description="Max narration words")
    min_image_prompt_words: int = Field(30, ge=10, le=100, description="Min image prompt words")
    max_image_prompt_words: int = Field(60, ge=10, le=200, description="Max image prompt words")
    
    # === Media Parameters ===
    # Note: media_width and media_height are auto-determined from template meta tags
    media_workflow: Optional[str] = Field(None, description="Custom media workflow (image or video)")
    
    # === Video Parameters ===
    video_fps: int = Field(30, ge=15, le=60, description="Video FPS")
    
    # === Frame Template (determines video size) ===
    frame_template: Optional[str] = Field(
        None, 
        description="HTML template path with size (e.g., '1080x1920/default.html'). Video size is auto-determined from template."
    )
    
    # === Template Custom Parameters ===
    template_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom template parameters (e.g., {'accent_color': '#ff0000', 'background': 'url'}). "
                    "Available parameters depend on the template. Use GET /api/templates/{template_path}/params to discover them."
    )
    
    # === Media Style ===
    prompt_prefix: Optional[str] = Field(None, description="Media style prefix")
    
    # === BGM ===
    bgm_path: Optional[str] = Field(None, description="Background music path")
    bgm_volume: float = Field(0.3, ge=0.0, le=1.0, description="BGM volume (0.0-1.0)")

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return enforce_safe_generation_text(value, field_name="text")

    @field_validator("research_topic", "prompt_prefix", "title")
    @classmethod
    def validate_optional_generation_text(cls, value: Optional[str], info):
        if value and value.strip():
            enforce_safe_generation_text(value, field_name=info.field_name)
        return value

    @field_validator(
        "bgm_path",
        "tts_workflow",
        "media_workflow",
        "frame_template",
    )
    @classmethod
    def validate_project_relative_reference(cls, value: Optional[str], info):
        if not value:
            return value
        path = Path(value)
        if path.is_absolute() or path.drive or ".." in path.parts or "\x00" in value:
            raise ValueError(f"{info.field_name} must be a project-relative resource")
        return value

    @field_validator("ref_audio")
    @classmethod
    def validate_reference_audio(cls, value: Optional[str]):
        return validate_reference_audio_path(value)

    @model_validator(mode="after")
    def validate_generation_contract(self):
        if self.min_narration_words > self.max_narration_words:
            raise ValueError("min_narration_words must not exceed max_narration_words")
        if self.min_image_prompt_words > self.max_image_prompt_words:
            raise ValueError("min_image_prompt_words must not exceed max_image_prompt_words")
        if self.confirmed_storyboard:
            indexes = [scene.index for scene in self.confirmed_storyboard]
            if len(indexes) != len(set(indexes)):
                raise ValueError("confirmed storyboard scene indexes must be unique")
            prompts = [
                scene.media_prompt or scene.visual_description
                for scene in self.confirmed_storyboard
                if scene.media_prompt or scene.visual_description
            ]
            if duplicate_prompt_groups(prompts):
                raise ValueError(
                    "confirmed storyboard prompts must be unique across scenes; "
                    "regenerate duplicate prompts"
                )
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Atomic Habits teaches us that small changes compound over time to produce remarkable results.",
                "mode": "generate",
                "n_scenes": 5,
                "frame_template": "1080x1920/image_default.html",
                "template_params": {
                    "accent_color": "#3498db",
                    "background": "https://example.com/custom-bg.jpg"
                },
                "title": "The Power of Atomic Habits"
            }
        }


class VideoGenerateResponse(BaseModel):
    """Video generation response (synchronous)"""
    success: bool = True
    message: str = "Success"
    video_url: str = Field(..., description="URL to access generated video")
    duration: float = Field(..., description="Video duration in seconds")
    file_size: int = Field(..., description="File size in bytes")


class VideoGenerateAsyncResponse(BaseModel):
    """Video generation async response"""
    success: bool = True
    message: str = "Task created successfully"
    task_id: str = Field(..., description="Task ID for tracking progress")

