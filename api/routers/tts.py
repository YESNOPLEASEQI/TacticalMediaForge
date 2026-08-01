"""
TTS (Text-to-Speech) endpoints
"""

import uuid

from fastapi import APIRouter, Request
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.public_paths import to_public_file_url
from api.schemas.tts import TTSSynthesizeRequest, TTSSynthesizeResponse
from military_video_gen.utils.media_validation import validate_generated_output
from military_video_gen.utils.os_util import get_output_path

router = APIRouter(prefix="/tts", tags=["Basic Services"])


@router.post("/synthesize", response_model=TTSSynthesizeResponse)
async def tts_synthesize(
    request: TTSSynthesizeRequest,
    military_video_gen: MilitaryVideoGenDep,
    http_request: Request,
):
    """
    Text-to-Speech synthesis endpoint
    
    Convert text to speech audio using ComfyUI workflows.
    
    - **text**: Text to synthesize
    - **workflow**: TTS workflow key (optional, uses default if not specified)
    - **ref_audio**: Reference audio for voice cloning (optional)
    - **voice_id**: (Deprecated) Voice ID for legacy compatibility
    
    Returns path to generated audio file and duration.
    
    Examples:
    ```json
    {
        "text": "Hello, welcome to MilitaryVideoGen!",
        "workflow": "runninghub/tts_edge.json"
    }
    ```
    
    With voice cloning:
    ```json
    {
        "text": "Hello, this is a cloned voice",
        "workflow": "runninghub/tts_index2.json",
        "ref_audio": "path/to/reference.wav"
    }
    ```
    """
    try:
        logger.info(f"TTS synthesis request accepted ({len(request.text)} chars)")
        
        # Build TTS parameters
        tts_params = {
            "text": request.text,
            "output_path": get_output_path("api_tts", f"{uuid.uuid4().hex}.mp3"),
        }
        
        # Add workflow if specified
        if request.workflow:
            tts_params["workflow"] = request.workflow
        
        # Add ref_audio if specified
        if request.ref_audio:
            tts_params["ref_audio"] = request.ref_audio
        
        # Legacy voice_id support (deprecated)
        if request.voice_id and not request.workflow:
            logger.warning("voice_id parameter is deprecated, please use workflow instead")
            tts_params["voice"] = request.voice_id
        
        # Call TTS service
        audio_path = await military_video_gen.tts(**tts_params)
        
        audio_file, duration = validate_generated_output(audio_path, media_kind="audio")
        assert duration is not None

        return TTSSynthesizeResponse(
            audio_path=to_public_file_url(http_request, audio_file),
            duration=duration
        )
        
    except Exception as e:
        raise internal_server_error("TTS synthesis error", e)

