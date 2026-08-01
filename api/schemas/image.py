"""
Image generation API schemas
"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from military_video_gen.utils.safety import enforce_safe_generation_text


class ImageGenerateRequest(BaseModel):
    """Image generation request"""
    prompt: str = Field(..., min_length=1, max_length=20_000, description="Image generation prompt")
    width: int = Field(1024, ge=512, le=2048, description="Image width")
    height: int = Field(1024, ge=512, le=2048, description="Image height")
    workflow: Optional[str] = Field(None, description="Custom workflow filename")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return enforce_safe_generation_text(value, field_name="prompt")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A serene mountain landscape at sunset, photorealistic style",
                "width": 1024,
                "height": 1024
            }
        }


class ImageGenerateResponse(BaseModel):
    """Image generation response"""
    success: bool = True
    message: str = "Success"
    image_path: str = Field(..., description="Path to generated image")

