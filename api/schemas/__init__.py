"""
API Schemas (Pydantic models)
"""

from api.schemas.base import BaseResponse, ErrorResponse
from api.schemas.content import (
    ImagePromptGenerateRequest,
    ImagePromptGenerateResponse,
    NarrationGenerateRequest,
    NarrationGenerateResponse,
    TitleGenerateRequest,
    TitleGenerateResponse,
)
from api.schemas.image import ImageGenerateRequest, ImageGenerateResponse
from api.schemas.llm import LLMChatRequest, LLMChatResponse
from api.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from api.schemas.video import (
    VideoGenerateAsyncResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)

__all__ = [
    # Base
    "BaseResponse",
    "ErrorResponse",
    # LLM
    "LLMChatRequest",
    "LLMChatResponse",
    # TTS
    "TTSSynthesizeRequest",
    "TTSSynthesizeResponse",
    # Image
    "ImageGenerateRequest",
    "ImageGenerateResponse",
    # Content
    "NarrationGenerateRequest",
    "NarrationGenerateResponse",
    "ImagePromptGenerateRequest",
    "ImagePromptGenerateResponse",
    "TitleGenerateRequest",
    "TitleGenerateResponse",
    # Video
    "VideoGenerateRequest",
    "VideoGenerateResponse",
    "VideoGenerateAsyncResponse",
]

