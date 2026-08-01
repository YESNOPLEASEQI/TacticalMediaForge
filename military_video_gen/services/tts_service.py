"""
TTS (Text-to-Speech) Service - Supports both local and ComfyUI inference
"""

import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from military_video_gen.services.comfy_base_service import ComfyBaseService
from military_video_gen.tts_voices import speed_to_rate
from military_video_gen.utils.async_utils import run_async_until_stopped
from military_video_gen.utils.media_validation import validate_generated_output
from military_video_gen.utils.os_util import get_output_path
from military_video_gen.utils.safety import (
    redact_path_for_log,
    redact_url_for_log,
    sanitize_error_message,
)
from military_video_gen.utils.tts_util import edge_tts


class TTSService(ComfyBaseService):
    """
    TTS (Text-to-Speech) service - Workflow-based
    
    Uses ComfyKit to execute TTS workflows.
    
    Usage:
        # Use default workflow
        audio_path = await military_video_gen.tts(text="Hello, world!")
        
        # Use specific workflow
        audio_path = await military_video_gen.tts(
            text="你好，世界！",
            workflow="tts_edge.json"
        )
        
        # List available workflows
        workflows = military_video_gen.tts.list_workflows()
    """
    
    WORKFLOW_PREFIX = "tts_"
    DEFAULT_WORKFLOW = None  # No hardcoded default, must be configured
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        Initialize TTS service
        
        Args:
            config: Full application config dict
            core: MilitaryVideoGenCore instance (for accessing shared ComfyKit)
        """
        super().__init__(config, service_name="tts", core=core)
    
    
    async def __call__(
        self,
        text: str,
        workflow: Optional[str] = None,
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        # TTS parameters
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        # Inference mode override
        inference_mode: Optional[str] = None,
        # Output path
        output_path: Optional[str] = None,
        **params
    ) -> str:
        """
        Generate speech using local Edge TTS or ComfyUI workflow
        
        Args:
            text: Text to convert to speech
            workflow: Workflow filename (for ComfyUI mode, default: from config)
            comfyui_url: ComfyUI URL (optional, overrides config)
            runninghub_api_key: RunningHub API key (optional, overrides config)
            voice: Voice ID (for local mode: Edge TTS voice ID; for ComfyUI: workflow-specific)
            speed: Speech speed multiplier (1.0 = normal, >1.0 = faster, <1.0 = slower)
            inference_mode: Override inference mode ("local" or "comfyui", default: from config)
            output_path: Custom output path (auto-generated if None)
            **params: Additional workflow parameters
        
        Returns:
            Generated audio file path
        
        Examples:
            # Local inference (Edge TTS)
            audio_path = await military_video_gen.tts(
                text="Hello, world!",
                inference_mode="local",
                voice="zh-CN-YunjianNeural",
                speed=1.2
            )
            
            # ComfyUI inference
            audio_path = await military_video_gen.tts(
                text="你好，世界！",
                inference_mode="comfyui",
                workflow="runninghub/tts_edge.json"
            )
        """
        if output_path is None:
            output_path = get_output_path("tts", f"{uuid.uuid4().hex}.mp3")

        # Determine inference mode (param > config)
        mode = inference_mode or self.config.get("inference_mode", "local")
        
        # Route to appropriate implementation
        if mode == "local":
            audio_path = await self._call_local_tts(
                text=text,
                voice=voice,
                speed=speed,
                output_path=output_path
            )
        else:  # comfyui
            # 1. Resolve workflow (returns structured info)
            workflow_info = self._resolve_workflow(workflow=workflow)
            
            # 2. Execute ComfyUI workflow
            audio_path = await self._call_comfyui_workflow(
                workflow_info=workflow_info,
                text=text,
                comfyui_url=comfyui_url,
                runninghub_api_key=runninghub_api_key,
                voice=voice,
                speed=speed,
                output_path=output_path,
                **params
            )
        validated_path, _ = validate_generated_output(audio_path, media_kind="audio")
        return str(validated_path)
    
    async def _call_local_tts(
        self,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate speech using local Edge TTS
        
        Args:
            text: Text to convert to speech
            voice: Edge TTS voice ID (default: from config)
            speed: Speech speed multiplier (default: from config)
            output_path: Custom output path (auto-generated if None)
        
        Returns:
            Generated audio file path
        """
        # Get config defaults
        local_config = self.config.get("local", {})
        
        # Determine voice and speed (param > config)
        final_voice = voice or local_config.get("voice", "zh-CN-YunjianNeural")
        final_speed = speed if speed is not None else local_config.get("speed", 1.2)
        
        # Convert speed to rate parameter
        rate = speed_to_rate(final_speed)
        
        logger.info(f"🎙️  Using local Edge TTS: voice={final_voice}, speed={final_speed}x (rate={rate})")
        
        # Generate output path if not provided
        if not output_path:
            # Generate unique filename
            unique_id = uuid.uuid4().hex
            output_path = f"output/{unique_id}.mp3"
            
            # Ensure output directory exists
            Path("output").mkdir(parents=True, exist_ok=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Call Edge TTS
        try:
            await edge_tts(
                text=text,
                voice=final_voice,
                rate=rate,
                output_path=output_path
            )
            
            logger.info(
                f"✅ Generated audio (local Edge TTS): {redact_path_for_log(output_path)}"
            )
            return output_path
        
        except Exception as e:
            logger.error(f"Local TTS generation error: {sanitize_error_message(e)}")
            raise
    
    async def _call_comfyui_workflow(
        self,
        workflow_info: dict,
        text: str,
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        voice: Optional[str] = None,
        speed: float = 1.0,
        output_path: Optional[str] = None,
        **params
    ) -> str:
        """
        Generate speech using ComfyUI workflow
        
        Args:
            workflow_info: Workflow info dict from _resolve_workflow()
            text: Text to convert to speech
            comfyui_url: ComfyUI URL
            runninghub_api_key: RunningHub API key
            voice: Voice ID (workflow-specific)
            speed: Speech speed multiplier (workflow-specific)
            output_path: Custom output path (downloads if URL returned)
            **params: Additional workflow parameters
        
        Returns:
            Generated audio file path (local if output_path provided, otherwise URL)
        """
        logger.info(f"🎙️  Using workflow: {workflow_info['key']}")
        
        # 1. Build workflow parameters (ComfyKit config is now managed by core)
        workflow_params = {"text": text}
        
        # Add optional TTS parameters (only if explicitly provided and not None)
        if voice is not None:
            workflow_params["voice"] = voice
        if speed is not None and speed != 1.0:
            workflow_params["speed"] = speed
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameter keys: {sorted(workflow_params)}")
        
        # 3. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "runninghub" and "workflow_id" in workflow_info:
                # RunningHub: pass workflow_id
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing RunningHub TTS workflow: {workflow_input}")
            else:
                # Selfhost: pass file path
                workflow_input = workflow_info.get("_internal_path", workflow_info["path"])
                logger.info(
                    f"Executing selfhost TTS workflow: {redact_path_for_log(workflow_input)}"
                )
            
            result = await run_async_until_stopped(kit.execute(workflow_input, workflow_params))
            
            # 4. Handle result
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"TTS generation failed: {sanitize_error_message(error_msg)}")
                raise RuntimeError(
                    f"TTS generation failed: {sanitize_error_message(error_msg)}"
                )
            
            # ComfyKit result can have audio files in different output types
            # Try to get audio file path from result
            audio_path = None
            
            # Check for audio files in result.audios (if available)
            if hasattr(result, 'audios') and result.audios:
                audio_path = result.audios[0]
                logger.debug(
                    f"✅ Found audio in result.audios: {redact_path_for_log(audio_path)}"
                )
            # Check for files in result.files
            elif hasattr(result, 'files') and result.files:
                audio_path = result.files[0]
                logger.debug(
                    f"✅ Found audio in result.files: {redact_path_for_log(audio_path)}"
                )
            # Check in outputs dictionary
            elif hasattr(result, 'outputs') and result.outputs:
                logger.debug(f"Searching result output keys: {sorted(result.outputs)}")
                # Try to find audio file in outputs
                for key, value in result.outputs.items():
                    if isinstance(value, str) and any(value.endswith(ext) for ext in ['.mp3', '.wav', '.flac']):
                        audio_path = value
                        logger.debug(
                            f"✅ Found audio in result.outputs[{key}]: "
                            f"{redact_path_for_log(audio_path)}"
                        )
                        break
            
            if not audio_path:
                logger.error(
                    "TTS result contained no usable audio "
                    f"(audios={bool(getattr(result, 'audios', None))}, "
                    f"files={bool(getattr(result, 'files', None))}, "
                    f"output_keys={sorted(getattr(result, 'outputs', {}) or {})})"
                )
                raise Exception("No audio file generated by workflow")
            
            # If output_path provided and audio_path is URL, download to local
            if output_path and audio_path.startswith(('http://', 'https://')):
                import os

                import httpx
                
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                logger.info(
                    f"Downloading audio from {redact_url_for_log(audio_path)} to "
                    f"{redact_path_for_log(output_path)}"
                )
                async with httpx.AsyncClient() as client:
                    response = await client.get(audio_path)
                    response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                
                logger.info(
                    f"✅ Generated audio (ComfyUI): {redact_path_for_log(output_path)}"
                )
                return output_path
            
            safe_audio_location = (
                redact_url_for_log(audio_path)
                if audio_path.startswith(("http://", "https://"))
                else redact_path_for_log(audio_path)
            )
            logger.info(f"✅ Generated audio (ComfyUI): {safe_audio_location}")
            return audio_path
        
        except Exception as e:
            logger.error(f"TTS generation error: {sanitize_error_message(e)}")
            raise
