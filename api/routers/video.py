"""
Video generation endpoints

Supports both synchronous and asynchronous video generation.
"""

import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import api_config
from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.public_paths import to_public_file_url
from api.schemas.video import (
    VideoGenerateAsyncResponse,
    VideoGenerateRequest,
    VideoGenerateResponse,
)
from api.tasks import TaskType, task_manager
from military_video_gen.database.models import Asset, Project
from military_video_gen.database.runtime_jobs import create_runtime_job
from military_video_gen.database.session import get_db_session
from military_video_gen.research.gate import enforce_verified_storyboard_gate
from military_video_gen.utils.media_validation import probe_media_file
from military_video_gen.utils.os_util import get_data_path
from military_video_gen.utils.safety import sanitize_error_message

router = APIRouter(prefix="/video", tags=["Video Generation"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def resolve_reference_image_paths(
    session: AsyncSession,
    request_body: VideoGenerateRequest,
) -> dict[str, list[str]]:
    """Resolve scene reference IDs to owned files without accepting client paths."""
    scenes = request_body.confirmed_storyboard or []
    scene_ids = {
        asset_id
        for scene in scenes
        for asset_id in scene.reference_asset_ids
    }
    if not scene_ids:
        return {}
    if not request_body.session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id is required when reference assets are selected",
        )

    project = await session.scalar(
        select(Project).where(
            Project.id == request_body.session_id,
            Project.deleted_at.is_(None),
        )
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project for reference assets not found")

    assets = list(
        (
            await session.scalars(
                select(Asset).where(
                    Asset.project_id == project.id,
                    Asset.id.in_(scene_ids),
                    Asset.asset_type == "image",
                    Asset.role == "visual_reference",
                    Asset.deleted_at.is_(None),
                )
            )
        ).all()
    )
    by_id = {asset.id: asset for asset in assets}
    reference_root = Path(get_data_path("projects", project.id, "references")).resolve()

    resolved_by_id: dict[str, str] = {}
    for asset_id in scene_ids:
        asset = by_id.get(asset_id)
        if asset is None or not asset.local_path:
            raise HTTPException(status_code=400, detail="Reference asset is not owned by the project")
        candidate = Path(asset.local_path).resolve()
        if not candidate.is_relative_to(reference_root) or not candidate.is_file():
            raise HTTPException(status_code=400, detail="Reference asset file is unavailable")
        resolved_by_id[asset_id] = str(candidate)

    return {
        str(scene.index): [resolved_by_id[asset_id] for asset_id in scene.reference_asset_ids]
        for scene in scenes
        if scene.reference_asset_ids
    }


def h3_generation_config(
    request_body: VideoGenerateRequest,
    military_video_gen,
) -> tuple[str, str | None]:
    """Return the configured H3 workflow and optional dedicated endpoint."""
    h3_config = (military_video_gen.config.get("comfyui") or {}).get("h3_reference") or {}
    if not h3_config.get("enabled", True):
        raise HTTPException(status_code=503, detail="MiniMax H3 reference mode is disabled")
    workflow = h3_config.get("workflow") or "selfhost/video_minimax_h3_reference.json"
    if request_body.media_workflow and request_body.media_workflow != workflow:
        raise HTTPException(
            status_code=400,
            detail="MiniMax H3 reference mode only accepts the configured H3 workflow",
        )
    return workflow, h3_config.get("comfyui_url") or None


def path_to_url(request: Request, file_path: str) -> str:
    """Convert an allowlisted local path to an accessible URL."""
    return to_public_file_url(request, file_path)


@router.post("/generate/sync", response_model=VideoGenerateResponse)
async def generate_video_sync(
    request_body: VideoGenerateRequest,
    military_video_gen: MilitaryVideoGenDep,
    request: Request,
    session: DBSession,
):
    """
    Generate video synchronously
    
    This endpoint blocks until video generation is complete.
    Suitable for small videos (< 30 seconds).
    
    **Note**: May timeout for large videos. Use `/generate/async` instead.
    
    Request body includes all video generation parameters.
    See VideoGenerateRequest schema for details.
    
    Returns path to generated video, duration, and file size.
    """
    await enforce_verified_storyboard_gate(session, request_body)
    reference_image_paths_by_scene = await resolve_reference_image_paths(session, request_body)
    h3_workflow, h3_comfyui_url = (
        h3_generation_config(request_body, military_video_gen)
        if request_body.reference_mode == "h3"
        else (None, None)
    )
    try:
        logger.info(
            f"Sync video generation request accepted ({len(request_body.text)} chars)"
        )
        
        # Auto-determine media_width and media_height from template meta tags (required)
        if not request_body.frame_template:
            raise ValueError("frame_template is required to determine media size")
        
        from military_video_gen.services.frame_html import HTMLFrameGenerator
        from military_video_gen.utils.template_util import resolve_template_path
        template_path = resolve_template_path(request_body.frame_template)
        generator = HTMLFrameGenerator(template_path)
        media_width, media_height = generator.get_media_size()
        logger.debug(f"Auto-determined media size from template: {media_width}x{media_height}")
        
        # Build video generation parameters
        video_params = {
            "text": request_body.text,
            "session_id": request_body.session_id,
            "confirmed_storyboard": (
                [scene.model_dump() for scene in request_body.confirmed_storyboard]
                if request_body.confirmed_storyboard
                else None
            ),
            "verification_mode": request_body.verification_mode,
            "research_topic": request_body.research_topic,
            "script_revision": request_body.script_revision,
            "mode": request_body.mode,
            "title": request_body.title,
            "n_scenes": request_body.n_scenes,
            "min_narration_words": request_body.min_narration_words,
            "max_narration_words": request_body.max_narration_words,
            "min_image_prompt_words": request_body.min_image_prompt_words,
            "max_image_prompt_words": request_body.max_image_prompt_words,
            "media_width": media_width,
            "media_height": media_height,
            "media_workflow": request_body.media_workflow,
            "video_fps": request_body.video_fps,
            "frame_template": request_body.frame_template,
            "prompt_prefix": request_body.prompt_prefix,
            "bgm_path": request_body.bgm_path,
            "bgm_volume": request_body.bgm_volume,
            "reference_mode": request_body.reference_mode,
            "reference_image_paths_by_scene": reference_image_paths_by_scene,
        }
        if h3_workflow:
            video_params["media_workflow"] = h3_workflow
            video_params["reference_comfyui_url"] = h3_comfyui_url
        
        # Add TTS workflow if specified
        if request_body.tts_workflow:
            video_params["tts_workflow"] = request_body.tts_workflow
        
        # Add ref_audio if specified
        if request_body.ref_audio:
            video_params["ref_audio"] = request_body.ref_audio
        
        # Legacy voice_id support (deprecated)
        if request_body.voice_id:
            logger.warning("voice_id parameter is deprecated, please use tts_workflow instead")
            video_params["voice_id"] = request_body.voice_id
        
        # Add custom template parameters if specified
        if request_body.template_params:
            video_params["template_params"] = request_body.template_params
        
        # Call video generator service
        result = await task_manager.run_limited(
            military_video_gen.generate_video,
            **video_params,
        )
        
        duration = probe_media_file(result.video_path, require_audio=True)
        file_size = os.path.getsize(result.video_path)
        
        # Convert path to URL
        video_url = path_to_url(request, result.video_path)
        
        return VideoGenerateResponse(
            video_url=video_url,
            duration=duration,
            file_size=file_size
        )
        
    except Exception as e:
        raise internal_server_error("Sync video generation error", e)


@router.post("/generate/async", response_model=VideoGenerateAsyncResponse)
async def generate_video_async(
    request_body: VideoGenerateRequest,
    military_video_gen: MilitaryVideoGenDep,
    request: Request,
    session: DBSession,
):
    """
    Generate video asynchronously
    
    Creates a background task for video generation.
    Returns immediately with a task_id for tracking progress.
    
    **Workflow:**
    1. Submit video generation request
    2. Receive task_id in response
    3. Poll `/api/tasks/{task_id}` to check status
    4. When status is "completed", retrieve video from result
    
    Request body includes all video generation parameters.
    See VideoGenerateRequest schema for details.
    
    Returns task_id for tracking progress.
    """
    await enforce_verified_storyboard_gate(session, request_body)
    reference_image_paths_by_scene = await resolve_reference_image_paths(session, request_body)
    h3_workflow, h3_comfyui_url = (
        h3_generation_config(request_body, military_video_gen)
        if request_body.reference_mode == "h3"
        else (None, None)
    )
    try:
        logger.info(
            f"Async video generation request accepted ({len(request_body.text)} chars)"
        )
        
        # Reuse an identical active request so client/network retries do not
        # create duplicate provider work.
        task, created = task_manager.create_or_get_task(
            task_type=TaskType.VIDEO_GENERATION,
            request_params=request_body.model_dump()
        )
        if not created:
            return VideoGenerateAsyncResponse(task_id=task.task_id)
        if request_body.session_id:
            try:
                persisted = await create_runtime_job(
                    project_id=request_body.session_id,
                    task=task,
                    job_type="video_generation",
                )
                if not persisted:
                    raise ValueError("project session was not found")
            except Exception as exc:
                task_manager.discard_pending_task(task.task_id)
                logger.error(
                    f"Could not persist pending video job {task.task_id}: "
                    f"{sanitize_error_message(exc)}"
                )
                raise
        
        # Define async execution function
        async def execute_video_generation():
            """Execute video generation in background"""
            # Auto-determine media_width and media_height from template meta tags (required)
            if not request_body.frame_template:
                raise ValueError("frame_template is required to determine media size")
            
            from military_video_gen.services.frame_html import HTMLFrameGenerator
            from military_video_gen.utils.template_util import resolve_template_path
            template_path = resolve_template_path(request_body.frame_template)
            generator = HTMLFrameGenerator(template_path)
            media_width, media_height = generator.get_media_size()
            logger.debug(f"Auto-determined media size from template: {media_width}x{media_height}")

            def progress_callback(event):
                message_map = {
                    "generating_narrations": "生成科普旁白",
                    "splitting_script": "拆分脚本分镜",
                    "generating_title": "生成任务标题",
                    "generating_image_prompts": "生成视觉提示词",
                    "processing_frame": "处理分镜素材",
                    "frame_step": "处理分镜素材",
                    "concatenating": "合成最终视频",
                    "completed": "任务完成",
                }
                action_map = {
                    "audio": "合成旁白音频",
                    "media": "生成/下载视觉素材",
                    "compose": "合成画面字幕",
                    "video": "渲染分镜视频",
                }

                message = message_map.get(event.event_type, event.event_type)
                if event.action:
                    message = action_map.get(event.action, message)
                if event.frame_current and event.frame_total:
                    message = f"{message}：第 {event.frame_current}/{event.frame_total} 个分镜"
                if event.extra_info:
                    message = f"{message} - {event.extra_info}"

                task_manager.update_progress(
                    task.task_id,
                    current=max(0, min(10000, int(event.progress * 10000))),
                    total=10000,
                    message=message,
                    stage=event.action or event.event_type,
                    current_scene=event.frame_current,
                    total_scenes=event.frame_total,
                )
            
            # Build video generation parameters
            video_params = {
                "text": request_body.text,
                "session_id": request_body.session_id,
                "confirmed_storyboard": (
                    [scene.model_dump() for scene in request_body.confirmed_storyboard]
                    if request_body.confirmed_storyboard
                    else None
                ),
                "verification_mode": request_body.verification_mode,
                "research_topic": request_body.research_topic,
                "script_revision": request_body.script_revision,
                "mode": request_body.mode,
                "title": request_body.title,
                "n_scenes": request_body.n_scenes,
                "min_narration_words": request_body.min_narration_words,
                "max_narration_words": request_body.max_narration_words,
                "min_image_prompt_words": request_body.min_image_prompt_words,
                "max_image_prompt_words": request_body.max_image_prompt_words,
                "media_width": media_width,
                "media_height": media_height,
                "media_workflow": request_body.media_workflow,
                "video_fps": request_body.video_fps,
                "frame_template": request_body.frame_template,
                "prompt_prefix": request_body.prompt_prefix,
                "bgm_path": request_body.bgm_path,
                "bgm_volume": request_body.bgm_volume,
                "reference_mode": request_body.reference_mode,
                "reference_image_paths_by_scene": reference_image_paths_by_scene,
                "progress_callback": progress_callback,
            }
            if h3_workflow:
                video_params["media_workflow"] = h3_workflow
                video_params["reference_comfyui_url"] = h3_comfyui_url
            
            # Add TTS workflow if specified
            if request_body.tts_workflow:
                video_params["tts_workflow"] = request_body.tts_workflow
            
            # Add ref_audio if specified
            if request_body.ref_audio:
                video_params["ref_audio"] = request_body.ref_audio
            
            # Legacy voice_id support (deprecated)
            if request_body.voice_id:
                logger.warning("voice_id parameter is deprecated, please use tts_workflow instead")
                video_params["voice_id"] = request_body.voice_id
            
            # Add custom template parameters if specified
            if request_body.template_params:
                video_params["template_params"] = request_body.template_params
            
            result = await military_video_gen.generate_video(**video_params)
            
            duration = probe_media_file(result.video_path, require_audio=True)
            file_size = os.path.getsize(result.video_path)
            
            # Convert path to URL
            video_url = path_to_url(request, result.video_path)
            
            return {
                "video_url": video_url,
                "duration": duration,
                "file_size": file_size,
                "reference_mode": request_body.reference_mode,
                "reference_asset_ids": [
                    asset_id
                    for scene in (request_body.confirmed_storyboard or [])
                    for asset_id in scene.reference_asset_ids
                ],
            }
        
        # Start execution
        await task_manager.execute_task(
            task_id=task.task_id,
            coro_func=execute_video_generation,
            timeout_seconds=(
                api_config.h3_task_timeout_seconds
                if request_body.reference_mode == "h3"
                else None
            ),
        )
        
        return VideoGenerateAsyncResponse(
            task_id=task.task_id
        )
        
    except Exception as e:
        raise internal_server_error("Async video generation error", e)

