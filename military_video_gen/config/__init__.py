"""
MilitaryVideoGen Configuration System

Unified configuration management with Pydantic validation.

Usage:
    from military_video_gen.config import config_manager
    
    # Access config (type-safe)
    api_key = config_manager.config.llm.api_key
    
    # Update config
    config_manager.update({"llm": {"api_key": "xxx"}})
    config_manager.save()
    
    # Validate
    if config_manager.validate():
        print("Config is valid!")
"""
from .loader import load_config_dict, save_config_dict
from .manager import ConfigManager
from .schema import (
    ComfyUIConfig,
    ImageSubConfig,
    LLMConfig,
    MilitaryVideoGenConfig,
    TTSSubConfig,
    VideoSubConfig,
)

# Global singleton instance
config_manager = ConfigManager()

__all__ = [
    "MilitaryVideoGenConfig",
    "LLMConfig", 
    "ComfyUIConfig",
    "TTSSubConfig",
    "ImageSubConfig",
    "VideoSubConfig",
    "ConfigManager",
    "config_manager",
    "load_config_dict",
    "save_config_dict",
]

