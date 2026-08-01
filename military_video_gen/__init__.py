"""
MilitaryVideoGen - AI-powered video generator

Convention-based system with unified configuration management.

Usage:
    from military_video_gen import military_video_gen
    
    # Initialize
    await military_video_gen.initialize()
    
    # Use capabilities
    answer = await military_video_gen.llm("Explain atomic habits")
    audio = await military_video_gen.tts("Hello world")
    
    # Generate video with different pipelines
    # Standard pipeline (default)
    result = await military_video_gen.generate_video(
        text="如何提高学习效率",
        n_scenes=5
    )
    
    # Custom pipeline (template for your own logic)
    result = await military_video_gen.generate_video(
        text=your_content,
        pipeline="custom",
        custom_param_example="custom_value"
    )
    
    # Check available pipelines
    print(military_video_gen.pipelines.keys())  # dict_keys(['standard', 'custom'])
"""

from military_video_gen.config import config_manager
from military_video_gen.service import MilitaryVideoGenCore, military_video_gen

__version__ = "0.2.0"

__all__ = ["MilitaryVideoGenCore", "military_video_gen", "config_manager"]
