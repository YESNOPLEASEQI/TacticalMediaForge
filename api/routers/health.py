"""
Health check and system info endpoints
"""

from fastapi import APIRouter
from pydantic import BaseModel

from military_video_gen.config import config_manager

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str = "0.1.0"
    service: str = "MilitaryVideoGen API"
    research_enabled: bool = False
    research_default_mode: str = "verified"
    runtime_contract: str = "english-storyboard-v2"


class CapabilitiesResponse(BaseModel):
    """Capabilities response"""
    success: bool = True
    capabilities: dict


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns service status and version information.
    """
    research = config_manager.config.research
    return HealthResponse(
        research_enabled=research.enabled,
        research_default_mode=research.default_mode,
    )


@router.get("/version", response_model=HealthResponse)
async def get_version():
    """
    Get API version
    
    Returns version information.
    """
    research = config_manager.config.research
    return HealthResponse(
        research_enabled=research.enabled,
        research_default_mode=research.default_mode,
    )

