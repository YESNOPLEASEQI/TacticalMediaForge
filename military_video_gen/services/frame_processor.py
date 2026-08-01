"""
Frame processor - Process single frame through complete pipeline

Orchestrates: TTS → Image Generation → Frame Composition → Video Segment

Key Feature:
- TTS-driven video duration: Audio duration from TTS is passed to video generation workflows
  to ensure perfect sync between audio and video (no padding, no trimming needed)
"""

import asyncio
import hashlib
import math
from pathlib import Path
from typing import Callable, Optional

import httpx
from loguru import logger

from military_video_gen.models.progress import ProgressEvent
from military_video_gen.models.storyboard import Storyboard, StoryboardConfig, StoryboardFrame
from military_video_gen.utils.async_utils import run_blocking_until_stopped
from military_video_gen.utils.safety import (
    enforce_safe_generation_fields,
    redact_path_for_log,
    redact_url_for_log,
    sanitize_error_message,
)
from military_video_gen.utils.subtitles import build_subtitle_cues


def normalize_video_duration(audio_duration: float) -> int:
    """Return a whole-second video target that never cuts narration short."""
    return max(1, math.ceil(audio_duration))


def wan_video_frame_count(duration_seconds: int, fps: int = 16) -> int:
    """Return a Wan-compatible 4n+1 frame count covering the target duration."""
    return max(1, duration_seconds) * fps + 1


def derive_video_seed(
    task_id: str | None, frame_index: int, *, base_seed: int | None = None
) -> int:
    """Return a stable but scene-unique 63-bit seed.

    ComfyUI caches identical graphs. A per-scene seed makes two intentionally
    similar prompts execute as independent generations while remaining
    reproducible inside one task.
    """
    if base_seed is not None:
        return (int(base_seed) + frame_index) % ((1 << 63) - 1)
    identity = f"{task_id or 'military-video'}:{frame_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(identity).digest()[:8], "big") & ((1 << 63) - 1)


class FrameProcessor:
    """Frame processor"""

    def __init__(self, military_video_gen_core):
        """
        Initialize

        Args:
            military_video_gen_core: MilitaryVideoGenCore instance
        """
        self.core = military_video_gen_core

    async def __call__(
        self,
        frame: StoryboardFrame,
        storyboard: "Storyboard",
        config: StoryboardConfig,
        total_frames: int = 1,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> StoryboardFrame:
        """
        Process single frame through complete pipeline

        Steps:
        1. Generate audio (TTS)
        2. Generate image (ComfyKit)
        3. Compose frame (add subtitle)
        4. Create video segment (image + audio)

        Args:
            frame: Storyboard frame to process
            storyboard: Storyboard instance
            config: Storyboard configuration
            total_frames: Total number of frames in storyboard
            progress_callback: Optional callback for progress updates (receives ProgressEvent)

        Returns:
            Processed frame with all paths filled
        """
        logger.info(f"Processing frame {frame.index}...")

        # Re-check generated content at the last trusted boundary before it is
        # sent to TTS or media providers. This also protects custom pipelines.
        enforce_safe_generation_fields(
            narration=frame.narration,
            media_prompt=frame.image_prompt,
        )

        frame_num = frame.index + 1

        # Determine if this frame needs image generation
        # If image_path or video_path is already set (e.g. asset-based pipeline), we consider it "has existing media" but skip generation
        has_existing_media = frame.image_path is not None or frame.video_path is not None
        needs_generation = frame.image_prompt is not None

        try:
            # Step 1: Generate audio (TTS)
            if not frame.audio_path:
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            event_type="frame_step",
                            progress=0.0,
                            frame_current=frame_num,
                            frame_total=total_frames,
                            step=1,
                            action="audio",
                        )
                    )
                await self._step_generate_audio(frame, config)
            else:
                logger.debug(
                    f"  1/4: Using existing audio: {redact_path_for_log(frame.audio_path)}"
                )

            # Step 2: Generate media (image or video, conditional)
            if needs_generation:
                if progress_callback:
                    progress_callback(
                        ProgressEvent(
                            event_type="frame_step",
                            progress=0.25,
                            frame_current=frame_num,
                            frame_total=total_frames,
                            step=2,
                            action="media",
                        )
                    )
                await self._step_generate_media(frame, config, progress_callback, total_frames)
            elif has_existing_media:
                # Log appropriate message based on media type
                if frame.video_path:
                    logger.debug(
                        f"  2/4: Using existing video: {redact_path_for_log(frame.video_path)}"
                    )
                else:
                    logger.debug(
                        f"  2/4: Using existing image: {redact_path_for_log(frame.image_path)}"
                    )
            else:
                frame.image_path = None
                frame.media_type = None
                logger.debug("  2/4: Skipped media generation (not required by template)")

            # Step 3: Compose frame (add subtitle)
            if progress_callback:
                progress_callback(
                    ProgressEvent(
                        event_type="frame_step",
                        progress=0.50 if (needs_generation or has_existing_media) else 0.33,
                        frame_current=frame_num,
                        frame_total=total_frames,
                        step=3,
                        action="compose",
                    )
                )
            await self._step_compose_frame(frame, storyboard, config)

            # Step 4: Create video segment
            if progress_callback:
                progress_callback(
                    ProgressEvent(
                        event_type="frame_step",
                        progress=0.75 if (needs_generation or has_existing_media) else 0.67,
                        frame_current=frame_num,
                        frame_total=total_frames,
                        step=4,
                        action="video",
                    )
                )

            await self._step_create_video_segment(frame, config)

            logger.info(f"✅ Frame {frame.index} completed")
            return frame

        except Exception as e:
            logger.error(f"❌ Failed to process frame {frame.index}: {sanitize_error_message(e)}")
            raise

    async def _step_generate_audio(self, frame: StoryboardFrame, config: StoryboardConfig):
        """Step 1: Generate audio using TTS"""
        logger.debug(f"  1/4: Generating audio for frame {frame.index}...")

        # Generate output path using task_id
        from military_video_gen.utils.os_util import get_task_frame_path

        output_path = get_task_frame_path(config.task_id, frame.index, "audio")

        # Build TTS params based on inference mode
        tts_params = {
            "text": frame.narration,
            "inference_mode": config.tts_inference_mode,
            "output_path": output_path,
            "index": frame.index + 1,  # 1-based index for workflow
        }

        if config.tts_inference_mode == "local":
            # Local mode: pass voice and speed
            if config.voice_id:
                tts_params["voice"] = config.voice_id
            if config.tts_speed is not None:
                tts_params["speed"] = config.tts_speed
        else:  # comfyui
            # ComfyUI mode: pass workflow, voice, speed, and ref_audio
            if config.tts_workflow:
                tts_params["workflow"] = config.tts_workflow
            if config.voice_id:
                tts_params["voice"] = config.voice_id
            if config.tts_speed is not None:
                tts_params["speed"] = config.tts_speed
            if config.ref_audio:
                tts_params["ref_audio"] = config.ref_audio

        audio_path = await self.core.tts(**tts_params)

        frame.audio_path = audio_path

        # Get audio duration
        frame.duration = await self._get_audio_duration(audio_path)
        frame.audio_duration = frame.duration

        logger.debug(
            f"  ✓ Audio generated: {redact_path_for_log(audio_path)} ({frame.duration:.2f}s)"
        )

    async def _step_generate_media(
        self,
        frame: StoryboardFrame,
        config: StoryboardConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        total_frames: int = 1,
    ):
        """Step 2: Generate media (image or video) using ComfyKit"""
        logger.debug(f"  2/4: Generating media for frame {frame.index}...")

        # Determine media type based on workflow/template.
        # video_ prefix in workflow name indicates ComfyUI video generation;
        # video_* templates can also use direct API video workflows.
        workflow_name = config.media_workflow or ""
        from military_video_gen.utils.template_util import get_template_type

        template_type = get_template_type(config.frame_template or "")
        is_video_workflow = "video_" in workflow_name.lower() or template_type == "video"
        media_type = "video" if is_video_workflow else "image"

        logger.debug(f"  → Media type: {media_type} (workflow: {workflow_name})")

        # Build media generation parameters
        from military_video_gen.utils.os_util import get_task_frame_path

        output_path = get_task_frame_path(config.task_id, frame.index, media_type)
        api_video_params = dict(config.api_video_params or {}) if media_type == "video" else {}
        if media_type == "video" and workflow_name.startswith("api/"):
            await self._prepare_api_video_inputs(frame, config, api_video_params)

        media_params = {
            "prompt": frame.image_prompt,
            "workflow": config.media_workflow,  # Pass workflow from config (None = use default)
            "media_type": media_type,
            "width": config.media_width,
            "height": config.media_height,
            "output_path": output_path,
            "image_path": frame.image_path,
            "index": frame.index + 1,  # 1-based index for workflow
        }
        media_params.update(api_video_params)
        if media_type == "video":
            media_params["seed"] = derive_video_seed(
                config.task_id,
                frame.index,
                base_seed=api_video_params.get("seed"),
            )

        # For video workflows: pass audio duration as target video duration
        # This ensures video length matches audio length from the source
        if is_video_workflow and frame.duration:
            target_duration = normalize_video_duration(frame.duration)
            media_params["duration"] = target_duration
            if workflow_name.replace("\\", "/").endswith("selfhost/video_wan2.1_fusionx.json"):
                media_params["video_length"] = wan_video_frame_count(target_duration)
            logger.info(
                f"  → Generating video with target duration: {target_duration}s "
                f"(audio: {frame.duration:.2f}s)"
            )

        # Call Media generation
        media_result = await self.core.media(**media_params)

        # Store media type
        frame.media_type = media_result.media_type

        if media_result.is_image:
            # Download image to local (pass task_id)
            local_path = await self._download_media(
                media_result.url,
                frame.index,
                config.task_id,
                media_type="image",
                progress_callback=progress_callback,
                total_frames=total_frames,
            )
            frame.image_path = local_path
            logger.debug(f"  ✓ Image generated: {redact_path_for_log(local_path)}")

        elif media_result.is_video:
            # Download video to local (pass task_id)
            local_path = await self._download_media(
                media_result.url,
                frame.index,
                config.task_id,
                media_type="video",
                progress_callback=progress_callback,
                total_frames=total_frames,
            )
            frame.video_path = local_path

            # Update duration from video if available
            if media_result.duration:
                frame.duration = media_result.duration
                logger.debug(
                    f"  ✓ Video generated: {redact_path_for_log(local_path)} "
                    f"(duration: {frame.duration:.2f}s)"
                )
            else:
                # Get video duration from file
                frame.duration = await self._get_video_duration(local_path)
                logger.debug(
                    f"  ✓ Video generated: {redact_path_for_log(local_path)} "
                    f"(duration: {frame.duration:.2f}s)"
                )

        else:
            raise ValueError(f"Unknown media type: {media_result.media_type}")

    async def _prepare_api_video_inputs(
        self,
        frame: StoryboardFrame,
        config: StoryboardConfig,
        api_video_params: dict,
    ) -> None:
        """Prepare provider-specific inputs for API video models."""
        from military_video_gen.utils.os_util import get_task_frame_path

        if api_video_params.pop("use_narration_audio_as_driving_audio", False):
            api_video_params["audio_path"] = frame.audio_path

        if (
            frame.image_path
            or api_video_params.get("first_clip_path")
            or api_video_params.get("first_video_path")
        ):
            return

        first_frame_workflow = api_video_params.pop("first_frame_workflow", None)
        if not first_frame_workflow:
            return

        first_frame_path = get_task_frame_path(config.task_id, frame.index, "image")
        logger.info(f"  → Generating API video first frame via {first_frame_workflow}")
        image_result = await self.core.media(
            prompt=frame.image_prompt,
            workflow=first_frame_workflow,
            media_type="image",
            width=config.media_width,
            height=config.media_height,
            output_path=first_frame_path,
            index=frame.index + 1,
        )
        frame.image_path = await self._download_media(
            image_result.url,
            frame.index,
            config.task_id,
            media_type="image",
        )

    async def _step_compose_frame(
        self, frame: StoryboardFrame, storyboard: "Storyboard", config: StoryboardConfig
    ):
        """Step 3: Compose frame with subtitle using HTML template"""
        logger.debug(f"  3/4: Composing frame {frame.index}...")

        # Generate output path using task_id
        from military_video_gen.utils.os_util import get_task_frame_path

        output_path = get_task_frame_path(config.task_id, frame.index, "composed")

        # For video type: render HTML as transparent overlay image
        # For image type: render HTML with image background
        # In both cases, we need the composed image
        audio_duration = frame.audio_duration
        if audio_duration <= 0 and frame.audio_path:
            audio_duration = await self._get_audio_duration(frame.audio_path)
            frame.audio_duration = audio_duration
        cues = build_subtitle_cues(frame.narration, audio_duration or frame.duration)
        if not cues:
            cues = build_subtitle_cues(frame.narration, 1.0)

        composed_paths: list[str] = []
        for cue_index, cue in enumerate(cues):
            cue_path = (
                output_path
                if len(cues) == 1
                else str(
                    Path(output_path).with_name(
                        f"{Path(output_path).stem}_{cue_index + 1:02d}{Path(output_path).suffix}"
                    )
                )
            )
            composed_paths.append(
                await self._compose_frame_html(
                    frame,
                    storyboard,
                    config,
                    cue_path,
                    subtitle_text=cue.text,
                )
            )

        frame.composed_image_paths = composed_paths
        frame.composed_image_path = composed_paths[0]

        logger.debug(f"  ✓ Frame composed with {len(composed_paths)} subtitle card(s)")

    async def _compose_frame_html(
        self,
        frame: StoryboardFrame,
        storyboard: "Storyboard",
        config: StoryboardConfig,
        output_path: str,
        subtitle_text: Optional[str] = None,
    ) -> str:
        """Compose frame using HTML template"""
        from military_video_gen.services.frame_html import HTMLFrameGenerator
        from military_video_gen.utils.template_util import resolve_template_path

        # Resolve template path (handles various input formats)
        template_path = resolve_template_path(config.frame_template)

        # Build ext data
        ext = {
            "index": frame.index + 1,
            "author": "",
            "brand": "",
            "describe": "",
            "signature": "",
            "hide_branding": True,
        }

        # Add custom template parameters
        if config.template_params:
            ext.update(config.template_params)
            branding_keys = ("author", "brand", "describe", "signature")
            has_custom_branding = any(config.template_params.get(key) for key in branding_keys)
            if has_custom_branding and "hide_branding" not in config.template_params:
                ext["hide_branding"] = False

        # Generate frame using HTML (size is auto-parsed from template path)
        generator = HTMLFrameGenerator(template_path)

        # Use video_path for video media, image_path for images
        media_path = frame.video_path if frame.media_type == "video" else frame.image_path
        logger.debug(
            "Generating frame with media: "
            f"'{redact_path_for_log(media_path)}' (type: {frame.media_type})"
        )

        composed_path = await generator.generate_frame(
            title=storyboard.title,
            text=frame.narration if subtitle_text is None else subtitle_text,
            image=media_path,  # HTMLFrameGenerator handles both image and video paths
            ext=ext,
            output_path=output_path,
        )

        return composed_path

    async def _step_create_video_segment(self, frame: StoryboardFrame, config: StoryboardConfig):
        """Step 4: Create video segment from media + audio"""
        logger.debug(f"  4/4: Creating video segment for frame {frame.index}...")

        # Generate output path using task_id
        from military_video_gen.utils.os_util import get_task_frame_path

        output_path = get_task_frame_path(config.task_id, frame.index, "segment")

        from military_video_gen.services.video import VideoService

        video_service = VideoService()
        audio_duration = frame.audio_duration or frame.duration
        cues = build_subtitle_cues(frame.narration, audio_duration)
        overlay_paths = frame.composed_image_paths or [frame.composed_image_path]

        # Branch based on media type
        if frame.media_type == "video":
            # Video workflow: overlay HTML template on video, then add audio
            logger.debug("  → Using video-based composition with HTML overlay")

            # Step 1: Overlay transparent HTML image on video
            # The composed_image_path contains the rendered HTML with transparent background
            temp_video_with_overlay = (
                get_task_frame_path(config.task_id, frame.index, "video") + "_overlay.mp4"
            )

            try:
                if len(overlay_paths) > 1:
                    await run_blocking_until_stopped(
                        video_service.overlay_timed_images_on_video,
                        video=frame.video_path,
                        overlays=[
                            (path, cue.start, cue.end) for path, cue in zip(overlay_paths, cues)
                        ],
                        output=temp_video_with_overlay,
                        scale_mode="contain",
                    )
                else:
                    await run_blocking_until_stopped(
                        video_service.overlay_image_on_video,
                        video=frame.video_path,
                        overlay_image=frame.composed_image_path,
                        output=temp_video_with_overlay,
                        scale_mode="contain",
                    )

                segment_path = await run_blocking_until_stopped(
                    video_service.merge_audio_video,
                    video=temp_video_with_overlay,
                    audio=frame.audio_path,
                    output=output_path,
                    replace_audio=True,
                    audio_volume=1.0,
                )
            finally:
                Path(temp_video_with_overlay).unlink(missing_ok=True)

        elif frame.media_type == "image" or frame.media_type is None:
            # Image workflow: Use composed image directly
            # The asset_default.html template includes the image in the composition
            logger.debug("  → Using image-based composition")

            if len(overlay_paths) > 1:
                segment_path = await run_blocking_until_stopped(
                    video_service.create_video_from_timed_images,
                    images=[(path, cue.end - cue.start) for path, cue in zip(overlay_paths, cues)],
                    audio=frame.audio_path,
                    output=output_path,
                    fps=config.video_fps,
                )
            else:
                segment_path = await run_blocking_until_stopped(
                    video_service.create_video_from_image,
                    image=frame.composed_image_path,
                    audio=frame.audio_path,
                    output=output_path,
                    fps=config.video_fps,
                )

        else:
            raise ValueError(f"Unknown media type: {frame.media_type}")

        frame.video_segment_path = segment_path

        logger.debug(f"  ✓ Video segment created: {redact_path_for_log(segment_path)}")

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get audio duration in seconds"""
        try:
            # Try using ffmpeg-python
            import ffmpeg

            probe = ffmpeg.probe(audio_path)
            duration = float(probe["format"]["duration"])
            return duration
        except Exception as e:
            logger.warning(
                f"Failed to get audio duration: {sanitize_error_message(e)}, using estimate"
            )
            # Fallback: estimate based on file size (very rough)
            import os

            file_size = os.path.getsize(audio_path)
            # Assume ~16kbps for MP3, so 2KB per second
            estimated_duration = file_size / 2000
            return max(1.0, estimated_duration)  # At least 1 second

    async def _download_media(
        self,
        url: str,
        frame_index: int,
        task_id: str,
        media_type: str,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        total_frames: int = 1,
    ) -> str:
        """Download media (image or video) from URL to local file"""
        import os

        from military_video_gen.utils.media_validation import (
            validate_download_payload,
            validate_local_media_file,
            validate_project_media_path,
        )
        from military_video_gen.utils.os_util import get_task_frame_path

        output_path = get_task_frame_path(task_id, frame_index, media_type)

        if url.startswith("file://"):
            local_path = validate_project_media_path(url[7:])
            if not os.path.exists(local_path):
                raise FileNotFoundError(
                    f"Generated media file not found: {redact_path_for_log(local_path)}"
                )
            validate_local_media_file(local_path, media_kind=media_type)
            return str(local_path)

        if os.path.exists(url):
            local_path = validate_project_media_path(url)
            validate_local_media_file(local_path, media_kind=media_type)
            return str(local_path)

        timeout = httpx.Timeout(connect=10.0, read=60, write=60, pool=60)
        retry_statuses = {429, 502, 503, 504}
        is_comfy_view_url = "/view?" in url and "filename=" in url
        if is_comfy_view_url:
            from urllib.parse import urlsplit

            configured = (self.core.config.get("comfyui") or {}).get("comfyui_url")
            target = urlsplit(url)
            expected = urlsplit(configured or "")
            if not configured or (target.hostname, target.port) != (
                expected.hostname,
                expected.port,
            ):
                raise ValueError("ComfyUI media URL does not match the configured endpoint")
        else:
            from military_video_gen.research.crawlers.security import URLSafetyChecker

            url = await URLSafetyChecker().validate(url)
        max_attempts = 120 if is_comfy_view_url else 30

        # Local ComfyUI is often exposed through 127.0.0.1 SSH tunnels.
        # Disable environment proxy handling here, otherwise httpx can route
        # loopback /view downloads through a proxy layer and receive false 502s.
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    if progress_callback and attempt > 1:
                        progress_callback(
                            ProgressEvent(
                                event_type="frame_step",
                                progress=0.35,
                                frame_current=frame_index + 1,
                                frame_total=total_frames,
                                step=2,
                                action="media",
                                extra_info=f"等待远端素材可读 ({attempt}/{max_attempts})",
                            )
                        )

                    response = await client.get(url)
                    response.raise_for_status()

                    validate_download_payload(
                        response.content,
                        response.headers.get("content-type"),
                        media_kind=media_type,
                    )

                    try:
                        with open(output_path, "wb") as f:
                            f.write(response.content)
                        validate_local_media_file(output_path, media_kind=media_type)
                    except Exception:
                        Path(output_path).unlink(missing_ok=True)
                        raise

                    return output_path
                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    should_retry = status_code in retry_statuses and attempt < max_attempts
                    if not should_retry:
                        raise RuntimeError(
                            f"Media download returned HTTP {status_code}: {redact_url_for_log(url)}"
                        ) from None

                    delay = min(1.5 * attempt, 5.0)
                    logger.warning(
                        f"Media download returned HTTP {status_code}; "
                        f"retrying {attempt}/{max_attempts} in {delay:.1f}s: "
                        f"{redact_url_for_log(url)}"
                    )
                    await asyncio.sleep(delay)
                except (
                    httpx.ConnectError,
                    httpx.ReadError,
                    httpx.WriteError,
                    httpx.PoolTimeout,
                    httpx.ReadTimeout,
                ) as e:
                    if attempt >= max_attempts:
                        raise RuntimeError(
                            f"Media download failed with {type(e).__name__}: "
                            f"{redact_url_for_log(url)}"
                        ) from None

                    delay = min(1.5 * attempt, 5.0)
                    logger.warning(
                        f"Media download failed with {type(e).__name__}; "
                        f"retrying {attempt}/{max_attempts} in {delay:.1f}s: "
                        f"{redact_url_for_log(url)}"
                    )
                    await asyncio.sleep(delay)

        return output_path

    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration in seconds"""
        try:
            import ffmpeg

            probe = ffmpeg.probe(video_path)
            duration = float(probe["format"]["duration"])
            return duration
        except Exception as e:
            logger.warning(
                f"Failed to get video duration: {sanitize_error_message(e)}, using audio duration"
            )
            # Fallback: use audio duration if available
            return 1.0  # Default to 1 second if unable to determine
