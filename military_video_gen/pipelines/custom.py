"""
Custom Video Generation Pipeline

Template pipeline for creating your own custom video generation workflows.
This serves as a reference implementation showing how to extend BasePipeline.

For real projects, copy this file and modify it according to your needs.
"""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from military_video_gen.models.progress import ProgressEvent
from military_video_gen.models.storyboard import (
    ContentMetadata,
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
    VideoGenerationResult,
)
from military_video_gen.pipelines.base import BasePipeline
from military_video_gen.utils.async_utils import run_blocking_until_stopped
from military_video_gen.utils.media_validation import probe_media_file
from military_video_gen.utils.safety import (
    enforce_safe_generation_fields,
    redact_path_for_log,
    redact_url_for_log,
    sanitize_error_message,
)


def validate_custom_output(path: str | Path) -> tuple[int, float]:
    """Return authoritative output metadata or reject a corrupt final file."""
    video_path = Path(path)
    file_size = video_path.stat().st_size
    duration = probe_media_file(video_path, require_audio=True)
    return file_size, duration


class CustomPipeline(BasePipeline):
    """
    Custom video generation pipeline template

    This is a template showing how to create your own pipeline with custom logic.
    You can customize:
    - Content processing logic
    - Narration generation strategy
    - Image prompt generation (conditional based on template)
    - Frame composition
    - Video assembly

    KEY OPTIMIZATION: Conditional Image Generation
    -----------------------------------------------
    This pipeline supports automatic detection of template image requirements.
    If your template doesn't use {{image}}, the entire image generation pipeline
    can be skipped, providing:
      ⚡ Faster generation (no image API calls)
      💰 Lower cost (no LLM calls for image prompts)
      🚀 Reduced dependencies (no ComfyUI needed for text-only videos)

    Usage patterns:
      1. Text-only videos: Use templates/1080x1920/simple.html
      2. AI-generated images: Use templates with {{image}} placeholder
      3. Custom logic: Modify template or override the detection logic in your subclass

    Example usage:
        # 1. Create your own pipeline by copying this file
        # 2. Modify the __call__ method with your custom logic
        # 3. Register it in service.py or dynamically

        from military_video_gen.pipelines.custom import CustomPipeline
        military_video_gen.pipelines["my_custom"] = CustomPipeline(military_video_gen)

        # 4. Use it
        result = await military_video_gen.generate_video(
            text=your_content,
            pipeline="my_custom",
            # Your custom parameters here
        )
    """

    async def __call__(
        self,
        text: str,
        # === Custom Parameters ===
        # Add your own parameters here
        custom_param_example: str = "default_value",
        # === Standard Parameters (keep these for compatibility) ===
        tts_inference_mode: Optional[str] = None,  # "local" or "comfyui"
        voice_id: Optional[str] = None,  # Deprecated, use tts_voice
        tts_voice: Optional[str] = None,  # Voice ID for local mode
        tts_workflow: Optional[str] = None,
        tts_speed: float = 1.2,
        ref_audio: Optional[str] = None,
        media_workflow: Optional[str] = None,
        # Note: media_width and media_height are auto-determined from template
        frame_template: Optional[str] = None,
        video_fps: int = 30,
        output_path: Optional[str] = None,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.2,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> VideoGenerationResult:
        """
        Custom video generation workflow

        Customize this method to implement your own logic.

        Args:
            text: Input text (customize meaning as needed)
            custom_param_example: Your custom parameter
            (other standard parameters...)

        Returns:
            VideoGenerationResult

        Image Generation Logic:
            - image_*.html templates → automatically generates images
            - video_*.html templates → automatically generates videos
            - static_*.html templates → skips media generation (faster, cheaper)
            - To customize: Override the template type detection logic in your subclass
        """
        logger.info("Starting CustomPipeline")
        enforce_safe_generation_fields(text=text)
        logger.info(f"Input text length: {len(text)} chars")
        logger.info(f"Custom parameter: {custom_param_example}")

        # === Handle TTS parameter compatibility ===
        # Support both old API (voice_id) and new API (tts_inference_mode + tts_voice)
        final_voice_id = None
        final_tts_workflow = tts_workflow

        if tts_inference_mode:
            # New API from web UI
            if tts_inference_mode == "local":
                # Local Edge TTS mode - use tts_voice
                final_voice_id = tts_voice or "zh-CN-YunjianNeural"
                final_tts_workflow = None  # Don't use workflow in local mode
                logger.debug(f"TTS Mode: local (voice={final_voice_id})")
            elif tts_inference_mode == "comfyui":
                # ComfyUI workflow mode
                final_voice_id = None  # Don't use voice_id in ComfyUI mode
                # tts_workflow already set from parameter
                logger.debug(f"TTS Mode: comfyui (workflow={final_tts_workflow})")
        else:
            # Old API (backward compatibility)
            final_voice_id = voice_id or tts_voice or "zh-CN-YunjianNeural"
            # tts_workflow already set from parameter
            logger.debug(
                f"TTS Mode: legacy (voice_id={final_voice_id}, workflow={final_tts_workflow})"
            )

        # ========== Step 0: Setup ==========
        self._report_progress(progress_callback, "initializing", 0.05)

        # Create task directory
        from military_video_gen.utils.os_util import (
            create_task_output_dir,
            get_task_final_video_path,
        )

        task_dir, task_id = create_task_output_dir()
        logger.info(f"Task directory: {redact_path_for_log(task_dir)}")

        user_specified_output = None
        if output_path is None:
            output_path = get_task_final_video_path(task_id)
        else:
            user_specified_output = output_path
            output_path = get_task_final_video_path(task_id)

        # Determine frame template
        # Priority: explicit param > config default > hardcoded default
        if frame_template is None:
            template_config = self.core.config.get("template", {})
            frame_template = template_config.get("default_template", "1080x1920/default.html")

        # ========== Step 0.5: Check template requirements ==========
        # Detect template type by filename prefix
        from military_video_gen.services.frame_html import HTMLFrameGenerator
        from military_video_gen.utils.template_util import get_template_type, resolve_template_path

        template_name = Path(frame_template).name
        template_type = get_template_type(template_name)
        template_requires_image = template_type == "image"

        # Read media size from template meta tags
        template_path = resolve_template_path(frame_template)
        generator = HTMLFrameGenerator(template_path)
        media_width, media_height = generator.get_media_size()
        logger.info(f"📐 Media size from template: {media_width}x{media_height}")

        if template_type == "image":
            logger.info("📸 Template requires image generation")
        elif template_type == "video":
            logger.info("🎬 Template requires video generation")
        else:  # static
            logger.info("⚡ Static template - skipping media generation pipeline")
            logger.info("   💡 Benefits: Faster generation + Lower cost + No ComfyUI dependency")

        # ========== Step 1: Process content (CUSTOMIZE THIS) ==========
        self._report_progress(progress_callback, "processing_content", 0.10)

        # Example: Generate title using LLM
        from military_video_gen.utils.content_generators import generate_title

        title = await generate_title(self.llm, text, strategy="llm")
        enforce_safe_generation_fields(title=title)
        logger.info("Generated title")

        # Example: Split or generate narrations
        # Option A: Split by lines (for fixed script)
        narrations = [line.strip() for line in text.split("\n") if line.strip()]

        # Option B: Use LLM to generate narrations (uncomment to use)
        # from military_video_gen.utils.content_generators import generate_narrations_from_topic
        # narrations = await generate_narrations_from_topic(
        #     self.llm,
        #     topic=text,
        #     n_scenes=5,
        #     min_words=20,
        #     max_words=80
        # )

        enforce_safe_generation_fields(narrations=narrations)
        logger.info(f"Generated {len(narrations)} narrations")

        # ========== Step 2: Generate image prompts (CONDITIONAL - CUSTOMIZE THIS) ==========
        self._report_progress(progress_callback, "generating_image_prompts", 0.25)

        # IMPORTANT: Check if template is image type
        # If your template is static_*.html, you can skip this entire step!
        if template_requires_image:
            # Template requires images - generate image prompts using LLM
            from military_video_gen.utils.content_generators import generate_image_prompts

            image_prompts = await generate_image_prompts(
                self.llm, narrations=narrations, min_words=30, max_words=60
            )

            # Example: Apply custom prompt prefix
            from military_video_gen.utils.prompt_helper import build_image_prompt

            custom_prefix = "cinematic style, professional lighting"  # Customize this

            final_image_prompts = []
            for base_prompt in image_prompts:
                final_prompt = build_image_prompt(base_prompt, custom_prefix)
                final_image_prompts.append(final_prompt)

            logger.info(f"✅ Generated {len(final_image_prompts)} image prompts")
        else:
            # Template doesn't need images - skip image generation entirely
            final_image_prompts = [None] * len(narrations)
            logger.info("⚡ Skipped image prompt generation (template doesn't need images)")
            logger.info(
                f"   💡 Savings: {len(narrations)} LLM calls + {len(narrations)} image generations"
            )

        enforce_safe_generation_fields(media_prompts=final_image_prompts)

        # ========== Step 3: Create storyboard ==========
        config = StoryboardConfig(
            task_id=task_id,
            n_storyboard=len(narrations),
            min_narration_words=20,
            max_narration_words=80,
            min_image_prompt_words=30,
            max_image_prompt_words=60,
            video_fps=video_fps,
            tts_inference_mode=tts_inference_mode or "local",  # TTS inference mode (CRITICAL FIX)
            voice_id=final_voice_id,  # Use processed voice_id
            tts_workflow=final_tts_workflow,  # Use processed workflow
            tts_speed=tts_speed,
            ref_audio=ref_audio,
            media_width=media_width,
            media_height=media_height,
            media_workflow=media_workflow,
            frame_template=frame_template,
        )

        # Optional: Add custom metadata
        content_metadata = ContentMetadata(title=title, subtitle="Custom Pipeline Output")

        storyboard = Storyboard(
            title=title, config=config, content_metadata=content_metadata, created_at=datetime.now()
        )

        # Create frames
        for i, (narration, image_prompt) in enumerate(zip(narrations, final_image_prompts)):
            frame = StoryboardFrame(
                index=i, narration=narration, image_prompt=image_prompt, created_at=datetime.now()
            )
            storyboard.frames.append(frame)

        try:
            # ========== Step 4: Process each frame ==========
            # This is the standard frame processing logic
            # You can customize frame processing if needed

            for i, frame in enumerate(storyboard.frames):
                base_progress = 0.3
                frame_range = 0.5
                per_frame_progress = frame_range / len(storyboard.frames)

                self._report_progress(
                    progress_callback,
                    "processing_frame",
                    base_progress + (per_frame_progress * i),
                    frame_current=i + 1,
                    frame_total=len(storyboard.frames),
                )

                # Use core frame processor (standard logic)
                processed_frame = await self.core.frame_processor(
                    frame=frame,
                    storyboard=storyboard,
                    config=config,
                    total_frames=len(storyboard.frames),
                    progress_callback=None,
                )
                storyboard.total_duration += processed_frame.duration
                logger.info(f"Frame {i + 1} completed ({processed_frame.duration:.2f}s)")

            # ========== Step 5: Concatenate videos ==========
            self._report_progress(progress_callback, "concatenating", 0.85)
            segment_paths = [frame.video_segment_path for frame in storyboard.frames]

            from military_video_gen.services.video import VideoService

            video_service = VideoService()

            final_video_path = await run_blocking_until_stopped(
                video_service.concat_videos,
                videos=segment_paths,
                output=output_path,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                bgm_mode="loop",
            )

            storyboard.final_video_path = final_video_path
            storyboard.completed_at = datetime.now()

            # Copy to user-specified path if provided
            if user_specified_output:
                import shutil

                Path(user_specified_output).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(final_video_path, user_specified_output)
                logger.info(
                    f"Final video copied to: {redact_path_for_log(user_specified_output)}"
                )
                final_video_path = user_specified_output
                storyboard.final_video_path = user_specified_output

            logger.success(
                f"Custom pipeline video completed: {redact_path_for_log(final_video_path)}"
            )

            # ========== Step 6: Create result ==========
            self._report_progress(progress_callback, "completed", 1.0)

            file_size, storyboard.total_duration = validate_custom_output(final_video_path)

            result = VideoGenerationResult(
                video_path=final_video_path,
                storyboard=storyboard,
                duration=storyboard.total_duration,
                file_size=file_size,
            )

            logger.info("Custom pipeline completed")
            logger.info("Title generated successfully")
            logger.info(f"Duration: {storyboard.total_duration:.2f}s")
            logger.info(f"Size: {file_size / (1024 * 1024):.2f} MB")
            logger.info(f"Frames: {len(storyboard.frames)}")

            # ========== Step 7: Persist metadata and storyboard ==========
            await self._persist_task_data(
                storyboard=storyboard,
                result=result,
                input_params={
                    "text": text,
                    "custom_param_example": custom_param_example,
                    "voice_id": voice_id,
                    "tts_workflow": tts_workflow,
                    "tts_speed": tts_speed,
                    "ref_audio": ref_audio,
                    "media_workflow": media_workflow,
                    "frame_template": frame_template,
                    "bgm_path": bgm_path,
                    "bgm_volume": bgm_volume,
                },
            )

            return result

        except Exception as e:
            logger.error(f"Custom pipeline failed: {sanitize_error_message(e)}")
            raise

    # ==================== Persistence ====================

    async def _persist_task_data(
        self, storyboard: Storyboard, result: VideoGenerationResult, input_params: dict
    ):
        """
        Persist task metadata and storyboard to filesystem

        Args:
            storyboard: Complete storyboard
            result: Video generation result
            input_params: Input parameters used for generation
        """
        try:
            task_id = storyboard.config.task_id
            if not task_id:
                logger.warning("No task_id in storyboard, skipping persistence")
                return

            # Build metadata
            # If user didn't provide a title, use the generated one from storyboard
            input_with_title = input_params.copy()
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
                        str(
                            self.core.config.get("comfyui", {}).get(
                                "comfyui_url", "unknown"
                            )
                        )
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

    # ==================== Custom Helper Methods ====================
    # Add your own helper methods here

    async def _custom_content_analysis(self, text: str) -> dict:
        """
        Example: Custom content analysis logic

        You can add your own helper methods to process content,
        extract metadata, or perform custom transformations.
        """
        # Your custom logic here
        return {"processed": text, "metadata": {}}

    async def _custom_prompt_generation(self, context: str) -> str:
        """
        Example: Custom prompt generation logic

        Create specialized prompts based on your use case.
        """
        prompt = f"Generate content based on: {context}"
        response = await self.llm(prompt, temperature=0.7, max_tokens=500)
        return response.strip()


# ==================== Usage Examples ====================

"""
Example 1: Text-only video (no AI image generation)
---------------------------------------------------
from military_video_gen import military_video_gen
from military_video_gen.pipelines.custom import CustomPipeline

# Initialize
await military_video_gen.initialize()

# Register custom pipeline
military_video_gen.pipelines["my_custom"] = CustomPipeline(military_video_gen)

# Use text-only template - no image generation!
result = await military_video_gen.generate_video(
    text="Your content here",
    pipeline="my_custom",
    frame_template="1080x1920/simple.html"  # Template without {{image}}
)
# Benefits: ⚡ Fast, 💰 Cheap, 🚀 No ComfyUI needed


Example 2: AI-generated image video
---------------------------------------------------
# Use template with {{image}} - automatic image generation
result = await military_video_gen.generate_video(
    text="Your content here",
    pipeline="my_custom",
    frame_template="1080x1920/default.html"  # Template with {{image}}
)
# Will automatically generate images via LLM + ComfyUI


Example 3: Create your own pipeline class
----------------------------------------
from military_video_gen.pipelines.custom import CustomPipeline

class MySpecialPipeline(CustomPipeline):
    async def __call__(self, text: str, **kwargs):
        # Your completely custom logic
        logger.info("Running my special pipeline")
        
        # You can reuse parts from CustomPipeline or start from scratch
        # ...
        
        return result


Example 4: Inline custom pipeline
----------------------------------------
from military_video_gen.pipelines.base import BasePipeline

class QuickPipeline(BasePipeline):
    async def __call__(self, text: str, **kwargs):
        # Quick custom logic
        narrations = text.split('\\n')
        
        for narration in narrations:
            audio = await self.tts(narration)
            image = await self.image(prompt=f"illustration of {narration}")
            # ... process frame
        
        # ... concatenate and return
        return result

# Use immediately
military_video_gen.pipelines["quick"] = QuickPipeline(military_video_gen)
result = await military_video_gen.generate_video(text=content, pipeline="quick")
"""
