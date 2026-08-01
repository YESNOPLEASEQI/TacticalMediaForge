"""
FastAPI Dependencies

Provides dependency injection for MilitaryVideoGenCore and other services.
"""

from typing import Annotated

from fastapi import Depends
from loguru import logger

from military_video_gen.service import MilitaryVideoGenCore

# Global MilitaryVideoGen instance
_military_video_gen_instance: MilitaryVideoGenCore = None


async def get_military_video_gen() -> MilitaryVideoGenCore:
    """
    Get MilitaryVideoGen core instance (dependency injection)
    
    Returns:
        MilitaryVideoGenCore instance
    """
    global _military_video_gen_instance
    
    if _military_video_gen_instance is None:
        _military_video_gen_instance = MilitaryVideoGenCore()
        await _military_video_gen_instance.initialize()
        logger.info("✅ MilitaryVideoGen initialized for API")
    
    return _military_video_gen_instance


async def shutdown_military_video_gen():
    """Shutdown MilitaryVideoGen instance and cleanup resources"""
    global _military_video_gen_instance
    if _military_video_gen_instance:
        logger.info("Shutting down MilitaryVideoGen...")
        await _military_video_gen_instance.cleanup()
        _military_video_gen_instance = None
    
    from military_video_gen.services.frame_html import HTMLFrameGenerator
    await HTMLFrameGenerator.close_browser()


# Type alias for dependency injection
MilitaryVideoGenDep = Annotated[MilitaryVideoGenCore, Depends(get_military_video_gen)]

