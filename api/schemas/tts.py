"""
TTS API schemas
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.schemas.base import validate_reference_audio_path
from military_video_gen.utils.safety import enforce_safe_generation_text


class TTSSynthesizeRequest(BaseModel):
    """TTS synthesis request"""
    text: str = Field(..., min_length=1, max_length=20_000, description="Text to synthesize")
    workflow: Optional[str] = Field(
        None, 
        description="TTS workflow key (e.g., 'runninghub/tts_edge.json' or 'selfhost/tts_edge.json'). If not specified, uses default workflow from config."
    )
    ref_audio: Optional[str] = Field(
        None, 
        description="Project-relative reference audio path for voice cloning (optional)."
    )
    voice_id: Optional[str] = Field(
        None, 
        description="Voice ID (deprecated, use workflow instead)"
    )

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return enforce_safe_generation_text(value, field_name="text")

    @field_validator("workflow")
    @classmethod
    def validate_project_relative_reference(cls, value: Optional[str], info):
        if not value:
            return value
        path = Path(value)
        if (
            path.is_absolute()
            or path.drive
            or ".." in path.parts
            or "\x00" in value
            or "://" in value
        ):
            raise ValueError(f"{info.field_name} must be a project-relative resource")
        return value

    @field_validator("ref_audio")
    @classmethod
    def validate_reference_audio(cls, value: Optional[str]):
        return validate_reference_audio_path(value)
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, welcome to MilitaryVideoGen!",
                "workflow": "runninghub/tts_edge.json",
                "ref_audio": None
            }
        }


class TTSSynthesizeResponse(BaseModel):
    """TTS synthesis response"""
    success: bool = True
    message: str = "Success"
    audio_path: str = Field(..., description="Path to generated audio file")
    duration: float = Field(..., description="Audio duration in seconds")

