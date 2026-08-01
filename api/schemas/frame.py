"""
Frame/Template rendering API schemas
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from military_video_gen.utils.safety import enforce_safe_generation_text


class FrameRenderRequest(BaseModel):
    """Frame rendering request"""
    template: str = Field(
        ..., 
        description="Template key (e.g., '1080x1920/default.html'). Can also be just filename (e.g., 'default.html') to use default size."
    )
    title: Optional[str] = Field(None, description="Frame title (optional)")
    text: str = Field(..., min_length=1, max_length=20_000, description="Frame text content")
    image: Optional[str] = Field(None, description="Image path or URL (optional)")

    @field_validator("title", "text")
    @classmethod
    def validate_visible_text(cls, value: Optional[str], info) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if info.field_name == "text" and not value:
            raise ValueError("text must not be blank")
        if value:
            return enforce_safe_generation_text(value, field_name=info.field_name)
        return value
    
    class Config:
        json_schema_extra = {
            "example": {
                "template": "1080x1920/default.html",
                "title": "Sample Title",
                "text": "This is a sample text for the frame.",
                "image": "resources/example.png"
            }
        }


class FrameRenderResponse(BaseModel):
    """Frame rendering response"""
    success: bool = True
    message: str = "Success"
    frame_path: str = Field(..., description="Path to generated frame image")
    width: int = Field(..., description="Frame width in pixels")
    height: int = Field(..., description="Frame height in pixels")


class TemplateParamConfig(BaseModel):
    """Single template parameter configuration"""
    type: str = Field(..., description="Parameter type: 'text', 'number', 'color', 'bool'")
    default: Any = Field(..., description="Default value")
    label: str = Field(..., description="Display label for the parameter")


class TemplateParamsResponse(BaseModel):
    """Template parameters response"""
    success: bool = True
    message: str = "Success"
    template: str = Field(..., description="Template path")
    media_width: int = Field(..., description="Media width from template meta tags")
    media_height: int = Field(..., description="Media height from template meta tags")
    params: Dict[str, TemplateParamConfig] = Field(
        default_factory=dict,
        description="Custom parameters defined in template. Key is parameter name, value is config."
    )

