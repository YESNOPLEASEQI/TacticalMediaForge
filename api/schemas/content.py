"""
Content generation API schemas
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from military_video_gen.utils.safety import enforce_safe_generation_text

# ============================================================================
# Narration Generation
# ============================================================================

class NarrationGenerateRequest(BaseModel):
    """Narration generation request"""
    text: str = Field(..., description="Source text to generate narrations from")
    n_scenes: int = Field(5, ge=1, le=20, description="Number of scenes")
    min_words: int = Field(5, ge=1, le=100, description="Minimum words per narration")
    max_words: int = Field(20, ge=1, le=200, description="Maximum words per narration")
    mode: Literal["reference", "quick"] = Field(
        "quick",
        description="Use available online references to enhance generation or generate directly with the configured LLM",
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return enforce_safe_generation_text(value, field_name="text")

    @model_validator(mode="after")
    def validate_word_range(self):
        if self.min_words > self.max_words:
            raise ValueError("min_words must not exceed max_words")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Atomic Habits is about making small changes that lead to remarkable results.",
                "n_scenes": 5,
                "min_words": 5,
                "max_words": 20
            }
        }


class NarrationGenerateResponse(BaseModel):
    """Narration generation response"""
    success: bool = True
    message: str = "Success"
    narrations: List[str] = Field(..., description="Generated narrations")


class ProjectNarrationGenerateRequest(NarrationGenerateRequest):
    project_id: str


class ContentJobResponse(BaseModel):
    job_id: str


class ResearchCreateRequest(BaseModel):
    project_id: str
    topic: str = Field(min_length=1)
    narrations: List[str] = Field(min_length=1)
    asset_type: Literal["image", "video"] = "video"
    mode: Literal["verified"] = "verified"
    script_revision: int = Field(default=0, ge=0)
    force_refresh: bool = False
    parent_job_id: Optional[str] = None

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
    def validate_narrations(cls, value: List[str]) -> List[str]:
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


class ResearchRetryRequest(BaseModel):
    parent_job_id: str
    force_refresh: bool = True
    request: Optional[ResearchCreateRequest] = None


# ============================================================================
# Image Prompt Generation
# ============================================================================

class ImagePromptGenerateRequest(BaseModel):
    """Image prompt generation request"""
    narrations: List[str] = Field(..., description="List of narrations")
    min_words: int = Field(30, ge=10, le=100, description="Minimum words per prompt")
    max_words: int = Field(60, ge=10, le=200, description="Maximum words per prompt")

    @field_validator("narrations", mode="before")
    @classmethod
    def validate_narration_container(cls, value):
        if not isinstance(value, list):
            raise ValueError("narrations must be a list")
        return value

    @field_validator("narrations")
    @classmethod
    def validate_narrations(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("narrations must not be empty")
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

    @model_validator(mode="after")
    def validate_word_range(self):
        if self.min_words > self.max_words:
            raise ValueError("min_words must not exceed max_words")
        return self
    
    class Config:
        json_schema_extra = {
            "example": {
                "narrations": [
                    "Small habits compound over time",
                    "Focus on systems, not goals"
                ],
                "min_words": 30,
                "max_words": 60
            }
        }


class ImagePromptGenerateResponse(BaseModel):
    """Image prompt generation response"""
    success: bool = True
    message: str = "Success"
    image_prompts: List[str] = Field(..., description="Generated image prompts")


class ProjectImagePromptGenerateRequest(ImagePromptGenerateRequest):
    project_id: str
    asset_type: Literal["image", "video"] = "video"


# ============================================================================
# Title Generation
# ============================================================================

class TitleGenerateRequest(BaseModel):
    """Title generation request"""
    text: str = Field(..., description="Source text")
    style: Optional[str] = Field(None, description="Title style (e.g., 'engaging', 'formal')")

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return enforce_safe_generation_text(value, field_name="text")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Atomic Habits is about making small changes that lead to remarkable results.",
                "style": "engaging"
            }
        }


class TitleGenerateResponse(BaseModel):
    """Title generation response"""
    success: bool = True
    message: str = "Success"
    title: str = Field(..., description="Generated title")

