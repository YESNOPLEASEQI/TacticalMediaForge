"""
Standard Video Generation Pipeline

Standard workflow for generating short videos from topic or fixed script.
This is the default pipeline for general-purpose video generation.
Refactored to use LinearVideoPipeline (Template Method Pattern).
"""

import asyncio
import hashlib
import shutil
from datetime import datetime
from pathlib import Path

from loguru import logger

from military_video_gen.models.progress import ProgressEvent
from military_video_gen.models.storyboard import (
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
    VideoGenerationResult,
)
from military_video_gen.pipelines.linear import LinearVideoPipeline, PipelineContext
from military_video_gen.prompts.legacy_contract import (
    contains_legacy_prompt,
    duplicate_prompt_groups,
)
from military_video_gen.services.video import VideoService
from military_video_gen.utils.async_utils import run_blocking_until_stopped
from military_video_gen.utils.content_generators import (
    generate_image_prompts,
    generate_narrations_from_topic,
    generate_title,
    generate_video_prompts,
    split_narration_script,
)
from military_video_gen.utils.media_validation import probe_media_file
from military_video_gen.utils.os_util import create_task_output_dir, get_task_final_video_path
from military_video_gen.utils.prompt_helper import build_image_prompt
from military_video_gen.utils.safety import (
    enforce_safe_generation_fields,
    redact_path_for_log,
    redact_url_for_log,
    sanitize_error_message,
)
from military_video_gen.utils.template_util import get_template_type


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_unique_generated_video_sources(frames: list[StoryboardFrame]) -> None:
    """Reject a timeline whose generated source clips are byte-identical."""
    seen: dict[str, int] = {}
    duplicates: list[tuple[int, int]] = []
    for frame in frames:
        if not frame.video_path:
            continue
        path = Path(frame.video_path)
        if not path.is_file():
            continue
        digest = _sha256_file(path)
        first_index = seen.get(digest)
        if first_index is None:
            seen[digest] = frame.index
        else:
            duplicates.append((first_index + 1, frame.index + 1))
    if duplicates:
        pairs = ", ".join(f"{first}/{second}" for first, second in duplicates)
        raise RuntimeError(
            "Generated video source clips are duplicated across scenes "
            f"({pairs}); refusing to build a looping final timeline"
        )


class StandardPipeline(LinearVideoPipeline):
    """
    Standard video generation pipeline

    Workflow:
    1. Generate/determine title
    2. Generate narrations (from topic or split fixed script)
    3. Generate image or video prompts for each narration
    4. For each frame:
       - Generate audio (TTS)
       - Generate media
       - Compose frame with template
       - Create video segment
    5. Concatenate all segments
    6. Add BGM (optional)

    Supports two modes:
    - "generate": LLM generates narrations from topic
    - "fixed": Use provided script as-is (each line = one narration)
    """

    # ==================== Lifecycle Methods ====================

    async def setup_environment(self, ctx: PipelineContext):
        """Step 1: Setup task directory and environment."""
        text = ctx.input_text
        mode = ctx.params.get("mode", "generate")

        confirmed_scenes = ctx.params.get("confirmed_storyboard") or []
        enforce_safe_generation_fields(
            text=text,
            prompt_prefix=ctx.params.get("prompt_prefix"),
            confirmed_narrations=[scene.get("narration", "") for scene in confirmed_scenes],
            confirmed_visuals=[scene.get("visual_description", "") for scene in confirmed_scenes],
            confirmed_media_prompts=[scene.get("media_prompt", "") for scene in confirmed_scenes],
        )

        logger.info(f"🚀 Starting StandardPipeline in '{mode}' mode")
        logger.info(f"   Text length: {len(text)} chars")

        # Create isolated task directory
        task_dir, task_id = create_task_output_dir()
        ctx.task_id = task_id
        ctx.task_dir = task_dir

        logger.info(f"📁 Task directory created: {redact_path_for_log(task_dir)}")
        logger.info(f"   Task ID: {task_id}")

        # Determine final video path
        output_path = ctx.params.get("output_path")
        if output_path is None:
            ctx.final_video_path = get_task_final_video_path(task_id)
        else:
            # We will copy to this path in finalize/post_production
            # For internal processing, we still use the task dir path?
            # Actually StandardPipeline logic used get_task_final_video_path as the target for concat
            # and then copied. Let's stick to that.
            ctx.final_video_path = get_task_final_video_path(task_id)
            logger.info(f"   Will copy final video to: {redact_path_for_log(output_path)}")

    async def generate_content(self, ctx: PipelineContext):
        """Step 2: Generate or process script/narrations."""
        confirmed_scenes = [
            scene
            for scene in (ctx.params.get("confirmed_storyboard") or [])
            if str(scene.get("narration") or "").strip()
        ]
        if confirmed_scenes:
            ctx.narrations = [str(scene["narration"]).strip() for scene in confirmed_scenes]
            enforce_safe_generation_fields(narrations=ctx.narrations)
            logger.info(f"Using {len(ctx.narrations)} user-confirmed narrations")
            return

        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text
        n_scenes = ctx.params.get("n_scenes", 5)
        min_words = ctx.params.get("min_narration_words", 5)
        max_words = ctx.params.get("max_narration_words", 20)

        if mode == "generate":
            self._report_progress(ctx.progress_callback, "generating_narrations", 0.05)
            ctx.narrations = await generate_narrations_from_topic(
                self.llm, topic=text, n_scenes=n_scenes, min_words=min_words, max_words=max_words
            )
            logger.info(f"✅ Generated {len(ctx.narrations)} narrations")
        else:  # fixed
            self._report_progress(ctx.progress_callback, "splitting_script", 0.05)
            split_mode = ctx.params.get("split_mode", "paragraph")
            ctx.narrations = await split_narration_script(text, split_mode=split_mode)
            logger.info(f"✅ Split script into {len(ctx.narrations)} segments (mode={split_mode})")
            logger.info(f"   Note: n_scenes={n_scenes} is ignored in fixed mode")

        enforce_safe_generation_fields(narrations=ctx.narrations)

    async def determine_title(self, ctx: PipelineContext):
        """Step 3: Determine or generate video title."""
        # Note: Swapped order with generate_content in base class call,
        # but in StandardPipeline original code, title was determined BEFORE narrations.
        # However, LinearVideoPipeline defines generate_content BEFORE determine_title.
        # This is fine as they are independent in StandardPipeline logic.

        title = ctx.params.get("title")
        mode = ctx.params.get("mode", "generate")
        text = ctx.input_text

        if title:
            ctx.title = title
            logger.info("   Using user-specified title")
        else:
            self._report_progress(ctx.progress_callback, "generating_title", 0.01)
            if mode == "generate":
                ctx.title = await generate_title(self.llm, text, strategy="auto")
                logger.info("   Auto-generated title")
            else:  # fixed
                ctx.title = await generate_title(self.llm, text, strategy="llm")
                logger.info("   LLM-generated title")

        enforce_safe_generation_fields(title=ctx.title)

    async def plan_visuals(self, ctx: PipelineContext):
        """Step 4: Generate media prompts or visual descriptions."""
        confirmed_scenes = [
            scene
            for scene in (ctx.params.get("confirmed_storyboard") or [])
            if str(scene.get("narration") or "").strip()
        ]
        confirmed_prompt_slots = [
            str(scene.get("media_prompt") or scene.get("visual_description") or "").strip()
            for scene in confirmed_scenes
        ]
        missing_prompt_indices = [
            index for index, prompt in enumerate(confirmed_prompt_slots) if not prompt
        ]
        if confirmed_scenes and not missing_prompt_indices:
            if any(contains_legacy_prompt(prompt) for prompt in confirmed_prompt_slots):
                raise ValueError(
                    "Confirmed storyboard contains a retired prompt contract; "
                    "regenerate the storyboard"
                )
            if duplicate_prompt_groups(confirmed_prompt_slots):
                raise ValueError(
                    "Confirmed storyboard contains duplicate prompts; "
                    "regenerate the storyboard"
                )
            ctx.image_prompts = confirmed_prompt_slots
            enforce_safe_generation_fields(media_prompts=ctx.image_prompts)
            logger.info(f"Using {len(ctx.image_prompts)} user-confirmed media prompts")
            return

        # Detect template type to determine if media generation is needed
        frame_template = ctx.params.get("frame_template") or "1080x1920/default.html"

        template_name = Path(frame_template).name
        template_type = get_template_type(template_name)
        template_requires_media = template_type in ["image", "video"]
        workflow_name = ctx.params.get("media_workflow") or ""
        workflow_filename = Path(workflow_name).name.lower()
        is_direct_api_workflow = workflow_name.lower().startswith("api/")
        is_comfy_video = not is_direct_api_workflow and (
            template_type == "video" or workflow_filename.startswith("video_")
        )

        if template_type == "image":
            logger.info("📸 Template requires image generation")
        elif template_type == "video":
            logger.info("🎬 Template requires video generation")
        else:  # static
            logger.info("⚡ Static template - skipping media generation pipeline")
            logger.info("   💡 Benefits: Faster generation + Lower cost + No ComfyUI dependency")

        # Generate media prompts only when the template requires image/video assets.
        if template_requires_media:
            progress_step = (
                "generating_video_prompts" if is_comfy_video else "generating_image_prompts"
            )
            self._report_progress(ctx.progress_callback, progress_step, 0.15)

            prompt_prefix = ctx.params.get("prompt_prefix")
            min_words = ctx.params.get("min_image_prompt_words", 30)
            max_words = ctx.params.get("max_image_prompt_words", 60)

            # Video prompts select a per-scene word range from estimated narration
            # duration. These bounds remain compatible with the public request.
            prompt_min_words = 35 if is_comfy_video else min_words
            prompt_max_words = 120 if is_comfy_video else max_words

            def media_prompt_progress(completed: int, total: int, message: str):
                batch_progress = completed / total if total > 0 else 0
                overall_progress = 0.15 + (batch_progress * 0.15)
                self._report_progress(
                    ctx.progress_callback, progress_step, overall_progress, extra_info=message
                )

            generation_indices = (
                missing_prompt_indices if confirmed_scenes else list(range(len(ctx.narrations)))
            )
            generation_narrations = [ctx.narrations[index] for index in generation_indices]

            if is_comfy_video:
                base_prompts = await generate_video_prompts(
                    self.llm,
                    narrations=generation_narrations,
                    min_words=prompt_min_words,
                    max_words=prompt_max_words,
                    progress_callback=media_prompt_progress,
                )
                config_section = "video"
            else:
                base_prompts = await generate_image_prompts(
                    self.llm,
                    narrations=generation_narrations,
                    min_words=prompt_min_words,
                    max_words=prompt_max_words,
                    progress_callback=media_prompt_progress,
                )
                config_section = "image"

            media_config = self.core.config.get("comfyui", {}).get(config_section, {})
            prompt_prefix_to_use = (
                ""
                if is_comfy_video
                else (
                    prompt_prefix
                    if prompt_prefix is not None
                    else media_config.get("prompt_prefix", "")
                )
            )
            if prompt_prefix is not None:
                logger.info(f"Using custom {config_section} prompt prefix")

            generated_prompts = [
                build_image_prompt(base_prompt, prompt_prefix_to_use)
                for base_prompt in base_prompts
            ]
            if confirmed_scenes:
                ctx.image_prompts = confirmed_prompt_slots.copy()
                for index, generated_prompt in zip(
                    generation_indices, generated_prompts, strict=True
                ):
                    ctx.image_prompts[index] = generated_prompt
            else:
                ctx.image_prompts = generated_prompts

            logger.info(f"✅ Generated {len(ctx.image_prompts)} {config_section} prompts")
        else:
            # Static template - skip image prompt generation entirely
            ctx.image_prompts = [None] * len(ctx.narrations)
            logger.info("⚡ Skipped image prompt generation (static template)")
            logger.info(
                f"   💡 Savings: {len(ctx.narrations)} LLM calls + {len(ctx.narrations)} media generations"
            )

        enforce_safe_generation_fields(media_prompts=ctx.image_prompts)

    async def initialize_storyboard(self, ctx: PipelineContext):
        """Step 5: Create Storyboard object and frames."""
        # === Handle TTS parameter compatibility ===
        tts_inference_mode = ctx.params.get("tts_inference_mode")
        tts_voice = ctx.params.get("tts_voice")
        voice_id = ctx.params.get("voice_id")
        tts_workflow = ctx.params.get("tts_workflow")

        final_voice_id = None
        final_tts_workflow = tts_workflow

        if tts_inference_mode:
            # New API from web UI
            if tts_inference_mode == "local":
                final_voice_id = tts_voice or "zh-CN-YunjianNeural"
                final_tts_workflow = None
                logger.debug(f"TTS Mode: local (voice={final_voice_id})")
            elif tts_inference_mode == "comfyui":
                final_voice_id = None
                logger.debug(f"TTS Mode: comfyui (workflow={final_tts_workflow})")
        else:
            # Old API
            final_voice_id = voice_id or tts_voice or "zh-CN-YunjianNeural"
            logger.debug(
                f"TTS Mode: legacy (voice_id={final_voice_id}, workflow={final_tts_workflow})"
            )

        # Create config
        ctx.config = StoryboardConfig(
            task_id=ctx.task_id,
            n_storyboard=len(ctx.narrations),  # Use actual length
            min_narration_words=ctx.params.get("min_narration_words", 5),
            max_narration_words=ctx.params.get("max_narration_words", 20),
            min_image_prompt_words=ctx.params.get("min_image_prompt_words", 30),
            max_image_prompt_words=ctx.params.get("max_image_prompt_words", 60),
            video_fps=ctx.params.get("video_fps", 30),
            tts_inference_mode=tts_inference_mode or "local",
            voice_id=final_voice_id,
            tts_workflow=final_tts_workflow,
            tts_speed=ctx.params.get("tts_speed", 1.2),
            ref_audio=ctx.params.get("ref_audio"),
            media_width=ctx.params.get("media_width"),
            media_height=ctx.params.get("media_height"),
            media_workflow=ctx.params.get("media_workflow"),
            api_video_params=ctx.params.get("api_video_params"),
            frame_template=ctx.params.get("frame_template") or "1080x1920/default.html",
            template_params=ctx.params.get("template_params"),
        )

        # Create storyboard
        ctx.storyboard = Storyboard(
            title=ctx.title,
            config=ctx.config,
            content_metadata=ctx.params.get("content_metadata"),
            created_at=datetime.now(),
        )

        # Create frames
        confirmed_scenes = [
            scene
            for scene in (ctx.params.get("confirmed_storyboard") or [])
            if str(scene.get("narration") or "").strip()
        ]
        for i, (narration, image_prompt) in enumerate(zip(ctx.narrations, ctx.image_prompts)):
            confirmed_scene = confirmed_scenes[i] if i < len(confirmed_scenes) else {}
            frame = StoryboardFrame(
                index=i,
                narration=narration,
                image_prompt=image_prompt,
                visual_description=confirmed_scene.get("visual_description"),
                estimated_duration=float(confirmed_scene.get("estimated_duration") or 0),
                media_type=confirmed_scene.get("asset_type"),
                research_metadata={
                    key: confirmed_scene.get(key)
                    for key in (
                        "research_job_id",
                        "subject_id",
                        "claim_ids",
                        "visual_fact_ids",
                        "field_provenance",
                        "fallback_level",
                        "verification_status",
                        "negative_constraints",
                        "warnings",
                    )
                    if confirmed_scene.get(key) is not None
                },
                created_at=datetime.now(),
            )
            ctx.storyboard.frames.append(frame)

    async def produce_assets(self, ctx: PipelineContext):
        """Step 6: Generate audio, images, and render frames (Core processing)."""
        storyboard = ctx.storyboard
        config = ctx.config

        # Check if using RunningHub workflows for parallel processing
        is_runninghub = (config.tts_workflow and config.tts_workflow.startswith("runninghub/")) or (
            config.media_workflow and config.media_workflow.startswith("runninghub/")
        )

        # Get concurrent limit from config_manager (supports hot reload without restart)
        from military_video_gen.config import config_manager

        runninghub_concurrent_limit = config_manager.config.comfyui.runninghub_concurrent_limit or 1

        if is_runninghub and runninghub_concurrent_limit > 1:
            logger.info(
                f"🚀 Using parallel processing for RunningHub workflows (max {runninghub_concurrent_limit} concurrent)"
            )

            semaphore = asyncio.Semaphore(runninghub_concurrent_limit)
            completed_count = 0

            async def process_frame_with_semaphore(i: int, frame: StoryboardFrame):
                nonlocal completed_count
                async with semaphore:
                    base_progress = 0.2
                    frame_range = 0.6
                    per_frame_progress = frame_range / len(storyboard.frames)

                    # Create frame-specific progress callback
                    def frame_progress_callback(event: ProgressEvent):
                        overall_progress = (
                            base_progress
                            + (per_frame_progress * completed_count)
                            + (per_frame_progress * event.progress)
                        )
                        if ctx.progress_callback:
                            adjusted_event = ProgressEvent(
                                event_type=event.event_type,
                                progress=overall_progress,
                                frame_current=i + 1,
                                frame_total=len(storyboard.frames),
                                step=event.step,
                                action=event.action,
                                extra_info=event.extra_info,
                            )
                            ctx.progress_callback(adjusted_event)

                    # Report frame start
                    self._report_progress(
                        ctx.progress_callback,
                        "processing_frame",
                        base_progress + (per_frame_progress * completed_count),
                        frame_current=i + 1,
                        frame_total=len(storyboard.frames),
                    )

                    processed_frame = await self.core.frame_processor(
                        frame=frame,
                        storyboard=storyboard,
                        config=config,
                        total_frames=len(storyboard.frames),
                        progress_callback=frame_progress_callback,
                    )

                    completed_count += 1
                    logger.info(
                        f"✅ Frame {i + 1} completed ({processed_frame.duration:.2f}s) [{completed_count}/{len(storyboard.frames)}]"
                    )
                    return i, processed_frame

            # Create all tasks and execute in parallel
            async with asyncio.TaskGroup() as group:
                tasks = [
                    group.create_task(process_frame_with_semaphore(i, frame))
                    for i, frame in enumerate(storyboard.frames)
                ]
            results = [task.result() for task in tasks]

            # Update frames in order and calculate total duration
            for idx, processed_frame in sorted(results, key=lambda x: x[0]):
                storyboard.frames[idx] = processed_frame
                storyboard.total_duration += processed_frame.duration

            logger.info(
                f"✅ All frames processed in parallel (total duration: {storyboard.total_duration:.2f}s)"
            )
        else:
            # Serial processing for non-RunningHub workflows
            logger.info("⚙️ Using serial processing (non-RunningHub workflow)")

            for i, frame in enumerate(storyboard.frames):
                base_progress = 0.2
                frame_range = 0.6
                per_frame_progress = frame_range / len(storyboard.frames)

                # Create frame-specific progress callback
                def frame_progress_callback(event: ProgressEvent):
                    overall_progress = (
                        base_progress
                        + (per_frame_progress * i)
                        + (per_frame_progress * event.progress)
                    )
                    if ctx.progress_callback:
                        adjusted_event = ProgressEvent(
                            event_type=event.event_type,
                            progress=overall_progress,
                            frame_current=event.frame_current,
                            frame_total=event.frame_total,
                            step=event.step,
                            action=event.action,
                            extra_info=event.extra_info,
                        )
                        ctx.progress_callback(adjusted_event)

                # Report frame start
                self._report_progress(
                    ctx.progress_callback,
                    "processing_frame",
                    base_progress + (per_frame_progress * i),
                    frame_current=i + 1,
                    frame_total=len(storyboard.frames),
                )

                processed_frame = await self.core.frame_processor(
                    frame=frame,
                    storyboard=storyboard,
                    config=config,
                    total_frames=len(storyboard.frames),
                    progress_callback=frame_progress_callback,
                )
                storyboard.total_duration += processed_frame.duration
                logger.info(f"✅ Frame {i + 1} completed ({processed_frame.duration:.2f}s)")

    async def post_production(self, ctx: PipelineContext):
        """Step 7: Concatenate videos and add BGM."""
        self._report_progress(ctx.progress_callback, "concatenating", 0.85)

        storyboard = ctx.storyboard
        assert_unique_generated_video_sources(storyboard.frames)
        segment_paths = [frame.video_segment_path for frame in storyboard.frames]

        video_service = VideoService()

        final_video_path = await run_blocking_until_stopped(
            video_service.concat_videos,
            videos=segment_paths,
            output=ctx.final_video_path,
            bgm_path=ctx.params.get("bgm_path"),
            bgm_volume=ctx.params.get("bgm_volume", 0.2),
            bgm_mode=ctx.params.get("bgm_mode", "loop"),
        )

        storyboard.final_video_path = final_video_path
        storyboard.completed_at = datetime.now()

        # Copy to user-specified path if provided
        user_specified_output = ctx.params.get("output_path")
        if user_specified_output:
            Path(user_specified_output).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_video_path, user_specified_output)
            logger.info(f"📹 Final video copied to: {redact_path_for_log(user_specified_output)}")
            ctx.final_video_path = user_specified_output
            storyboard.final_video_path = user_specified_output

        logger.success(
            f"🎬 Video generation completed: {redact_path_for_log(ctx.final_video_path)}"
        )

    async def finalize(self, ctx: PipelineContext) -> VideoGenerationResult:
        """Step 8: Create result object and persist metadata."""
        self._report_progress(ctx.progress_callback, "completed", 1.0)

        video_path_obj = Path(ctx.final_video_path)
        authoritative_duration = probe_media_file(video_path_obj, require_audio=True)
        file_size = video_path_obj.stat().st_size
        ctx.storyboard.total_duration = authoritative_duration

        result = VideoGenerationResult(
            video_path=ctx.final_video_path,
            storyboard=ctx.storyboard,
            duration=authoritative_duration,
            file_size=file_size,
        )

        ctx.result = result

        logger.info(f"✅ Generated video: {redact_path_for_log(ctx.final_video_path)}")
        logger.info(f"   Duration: {ctx.storyboard.total_duration:.2f}s")
        logger.info(f"   Size: {file_size / (1024 * 1024):.2f} MB")
        logger.info(f"   Frames: {len(ctx.storyboard.frames)}")

        # Persist metadata
        await self._persist_task_data(ctx)

        return result

    async def _persist_task_data(self, ctx: PipelineContext):
        """
        Persist task metadata and storyboard to filesystem
        """
        try:
            storyboard = ctx.storyboard
            result = ctx.result
            task_id = storyboard.config.task_id

            if not task_id:
                logger.warning("No task_id in storyboard, skipping persistence")
                return

            # Build metadata
            input_with_title = ctx.params.copy()
            input_with_title["text"] = ctx.input_text  # Ensure text is included
            if not input_with_title.get("title"):
                input_with_title["title"] = storyboard.title

            metadata = {
                "task_id": task_id,
                "created_at": storyboard.created_at.isoformat() if storyboard.created_at else None,
                "completed_at": storyboard.completed_at.isoformat()
                if storyboard.completed_at
                else None,
                "status": "completed",
                "input": input_with_title,
                "result": {
                    "video_path": result.video_path,
                    "duration": result.duration,
                    "file_size": result.file_size,
                    "n_frames": len(storyboard.frames),
                },
                "config": {
                    "llm_model": self.core.config.get("llm", {}).get("model", "unknown"),
                    "llm_base_url": redact_url_for_log(
                        str(self.core.config.get("llm", {}).get("base_url", "unknown"))
                    ),
                    "comfyui_url": redact_url_for_log(
                        str(self.core.config.get("comfyui", {}).get("comfyui_url", "unknown"))
                    ),
                    "runninghub_enabled": bool(
                        self.core.config.get("comfyui", {}).get("runninghub_api_key")
                    ),
                },
            }

            # Save metadata
            await self.core.persistence.save_task_metadata(task_id, metadata)
            logger.info(f"💾 Saved task metadata: {task_id}")

            # Save storyboard
            await self.core.persistence.save_storyboard(task_id, storyboard)
            logger.info(f"💾 Saved storyboard: {task_id}")

        except Exception as e:
            logger.error(f"Failed to persist task data: {sanitize_error_message(e)}")
            # Don't raise - persistence failure shouldn't break video generation
