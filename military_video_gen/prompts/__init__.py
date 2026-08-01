"""
Prompts package

Centralized prompt management for all LLM interactions.
"""

from military_video_gen.prompts.content_narration import build_content_narration_prompt
from military_video_gen.prompts.image_generation import (
    DEFAULT_IMAGE_STYLE,
    IMAGE_STYLE_PRESETS,
    build_image_prompt_prompt,
)
from military_video_gen.prompts.style_conversion import build_style_conversion_prompt
from military_video_gen.prompts.title_generation import build_title_generation_prompt
from military_video_gen.prompts.topic_narration import (
    build_topic_narration_prompt,
    build_topic_narrative_plan_prompt,
)

__all__ = [
    # Narration builders
    "build_topic_narration_prompt",
    "build_topic_narrative_plan_prompt",
    "build_content_narration_prompt",
    "build_title_generation_prompt",
    
    # Image builders
    "build_image_prompt_prompt",
    "build_style_conversion_prompt",
    
    # Image style presets
    "IMAGE_STYLE_PRESETS",
    "DEFAULT_IMAGE_STYLE",
]
