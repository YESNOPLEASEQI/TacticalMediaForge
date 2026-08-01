"""
Image generation endpoints
"""

import uuid

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.public_paths import to_public_file_url
from api.schemas.image import ImageGenerateRequest, ImageGenerateResponse
from military_video_gen.utils.media_validation import validate_generated_output
from military_video_gen.utils.os_util import get_output_path

router = APIRouter(prefix="/image", tags=["Basic Services"])


@router.post("/generate", response_model=ImageGenerateResponse)
async def image_generate(
    request: ImageGenerateRequest,
    military_video_gen: MilitaryVideoGenDep,
    http_request: Request,
):
    """
    Image generation endpoint
    
    Generate image from text prompt using ComfyKit.
    
    - **prompt**: Image description/prompt
    - **width**: Image width (512-2048)
    - **height**: Image height (512-2048)
    - **workflow**: Optional custom workflow filename
    
    Returns path to generated image.
    """
    try:
        logger.info(f"Image generation request accepted ({len(request.prompt)} chars)")
        
        # Call media service (backward compatible with image API)
        output_path = get_output_path("api_images", f"{uuid.uuid4().hex}.png")
        media_result = await military_video_gen.media(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            workflow=request.workflow,
            output_path=output_path,
        )
        
        # For backward compatibility, only support image results in /image endpoint
        if media_result.is_video:
            raise HTTPException(
                status_code=400,
                detail="Video workflow used. Please use /media/generate endpoint for video generation."
            )
        
        image_path, _ = validate_generated_output(media_result.url, media_kind="image")
        return ImageGenerateResponse(
            image_path=to_public_file_url(http_request, image_path)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise internal_server_error("Image generation error", e)

