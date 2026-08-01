"""
LLM API schemas
"""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from military_video_gen.utils.safety import enforce_safe_generation_text


class LLMChatRequest(BaseModel):
    """LLM chat request"""
    prompt: str = Field(..., min_length=1, max_length=20_000, description="User prompt")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature (0.0-2.0)")
    max_tokens: int = Field(2000, ge=1, le=32000, description="Maximum tokens")

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
                "prompt": "Explain the concept of atomic habits in 3 sentences",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }


class LLMChatResponse(BaseModel):
    """LLM chat response"""
    success: bool = True
    message: str = "Success"
    content: str = Field(..., description="Generated response")
    tokens_used: Optional[int] = Field(None, description="Tokens used (if available)")


class LLMConfigResponse(BaseModel):
    """LLM configuration response"""
    success: bool = True
    message: str = "Success"
    api_key_masked: str = Field("", description="Masked API key")
    has_api_key: bool = Field(False, description="Whether an API key is configured")
    base_url: str = Field("", description="LLM API Base URL")
    model: str = Field("", description="LLM model name")


class LLMConfigUpdateRequest(BaseModel):
    """LLM configuration update request"""
    api_key: Optional[str] = Field(
        None,
        description="New API key. Empty reuses the existing key only for the same Base URL.",
    )
    base_url: str = Field(..., description="LLM API Base URL")
    model: str = Field(..., description="LLM model name")


class LLMModelsRequest(BaseModel):
    """LLM model discovery request"""
    api_key: Optional[str] = Field(
        None,
        description="Optional API key. Empty reuses the current key only for the same Base URL.",
    )
    base_url: Optional[str] = Field(None, description="Optional base URL. Uses current config if empty.")


class LLMModelsResponse(BaseModel):
    """LLM model discovery response"""
    success: bool = True
    message: str = "Success"
    models: List[str] = Field(default_factory=list, description="Available model IDs")

