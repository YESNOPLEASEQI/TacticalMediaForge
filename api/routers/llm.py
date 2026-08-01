"""
LLM (Large Language Model) endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.schemas.llm import (
    LLMChatRequest,
    LLMChatResponse,
    LLMConfigResponse,
    LLMConfigUpdateRequest,
    LLMModelsRequest,
    LLMModelsResponse,
)
from military_video_gen.config import config_manager
from military_video_gen.utils.llm_util import fetch_available_models, normalize_openai_base_url
from military_video_gen.utils.safety import enforce_safe_generation_fields, sanitize_error_message

router = APIRouter(prefix="/llm", tags=["Basic Services"])


def mask_api_key(api_key: str) -> str:
    """Return a display-safe API key preview."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:3]}{'*' * 8}{api_key[-4:]}"


def resolve_api_key_for_base(
    requested_api_key: str | None,
    requested_base_url: str,
    current_config: dict,
) -> str:
    """Reuse a stored key only for the exact configured provider.

    Without this binding, a caller could supply an attacker-controlled Base URL
    and make model discovery exfiltrate the stored Bearer token.
    """
    explicit_key = (requested_api_key or "").strip()
    if explicit_key:
        return explicit_key

    requested_base = normalize_openai_base_url(requested_base_url).casefold()
    current_base = normalize_openai_base_url(current_config.get("base_url", "")).casefold()
    current_key = str(current_config.get("api_key", "") or "").strip()
    if current_key and requested_base and requested_base == current_base:
        return current_key
    if current_key and requested_base != current_base:
        raise ValueError("api_key must be provided when base_url changes")
    return ""


@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config():
    """Get display-safe LLM configuration."""
    try:
        config = config_manager.get_llm_config()
        api_key = config.get("api_key", "")
        return LLMConfigResponse(
            api_key_masked=mask_api_key(api_key),
            has_api_key=bool(api_key.strip()),
            base_url=config.get("base_url", ""),
            model=config.get("model", ""),
        )
    except Exception as e:
        raise internal_server_error("Get LLM config error", e)


@router.put("/config", response_model=LLMConfigResponse)
async def update_llm_config(request: LLMConfigUpdateRequest):
    """Update and persist LLM configuration."""
    try:
        current = config_manager.get_llm_config()
        base_url = normalize_openai_base_url(request.base_url)
        api_key = resolve_api_key_for_base(request.api_key, base_url, current)
        model = request.model.strip()

        if not base_url:
            raise ValueError("base_url is required")
        if not model:
            raise ValueError("model is required")

        config_manager.set_llm_config(api_key=api_key, base_url=base_url, model=model)
        config_manager.save()

        return LLMConfigResponse(
            message="LLM configuration saved",
            api_key_masked=mask_api_key(api_key),
            has_api_key=bool(api_key.strip()),
            base_url=base_url,
            model=model,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_error_message(e))
    except Exception as e:
        raise internal_server_error("Update LLM config error", e)


@router.post("/models", response_model=LLMModelsResponse)
async def list_llm_models(request: LLMModelsRequest):
    """Fetch available models from an OpenAI-compatible provider."""
    try:
        current = config_manager.get_llm_config()
        base_url = request.base_url.strip() if request.base_url and request.base_url.strip() else current.get("base_url", "")
        api_key = resolve_api_key_for_base(request.api_key, base_url, current)

        if not api_key:
            raise ValueError("api_key is required to fetch models")
        if not base_url:
            raise ValueError("base_url is required to fetch models")

        models = await run_in_threadpool(fetch_available_models, api_key, base_url)
        return LLMModelsResponse(models=models)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_error_message(e))
    except Exception as e:
        raise internal_server_error("List LLM models error", e)


@router.post("/chat", response_model=LLMChatResponse)
async def llm_chat(
    request: LLMChatRequest,
    military_video_gen: MilitaryVideoGenDep
):
    """
    LLM chat endpoint
    
    Generate text response using configured LLM.
    
    - **prompt**: User prompt/question
    - **temperature**: Creativity level (0.0-2.0, lower = more deterministic)
    - **max_tokens**: Maximum response length
    
    Returns generated text response.
    """
    try:
        logger.info(f"LLM chat request accepted ({len(request.prompt)} chars)")
        
        # Call LLM service
        response = await military_video_gen.llm(
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        enforce_safe_generation_fields(model_response=response)
        
        return LLMChatResponse(
            content=response,
            tokens_used=None  # Can add token counting if needed
        )
        
    except Exception as e:
        raise internal_server_error("LLM chat error", e)

