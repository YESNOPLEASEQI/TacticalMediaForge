"""
Configuration Manager - Singleton pattern

Provides unified access to configuration with automatic validation.
"""
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from military_video_gen.utils.safety import redact_path_for_log, sanitize_error_message

from .loader import load_config_dict, save_config_dict
from .schema import MilitaryVideoGenConfig


class ConfigManager:
    """
    Configuration Manager (Singleton)
    
    Provides unified access to configuration with automatic validation.
    """
    _instance: Optional['ConfigManager'] = None
    
    def __new__(cls, config_path: str = "config.yaml"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config_path: str = "config.yaml"):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self.config_path = Path(config_path)
        self.config: MilitaryVideoGenConfig = self._load()
        self._initialized = True
    
    def _load(self) -> MilitaryVideoGenConfig:
        """Load configuration from file"""
        data = load_config_dict(str(self.config_path))
        config = MilitaryVideoGenConfig(**data)
        
        # Validate template path exists
        self._validate_template(config.template.default_template)
        
        return config
    
    def _validate_template(self, template_path: str):
        """Validate that the configured template exists"""
        from military_video_gen.utils.template_util import resolve_template_path
        
        try:
            # Try to resolve the template path
            resolved_path = resolve_template_path(template_path)
            logger.debug(
                "Template validation passed: "
                f"{redact_path_for_log(template_path)} -> "
                f"{redact_path_for_log(resolved_path)}"
            )
        except FileNotFoundError as e:
            logger.warning(
                f"Configured default template '{template_path}' not found. "
                "Will fall back to the default template if needed. Error: "
                f"{sanitize_error_message(e)}"
            )
    
    def reload(self):
        """Reload configuration from file"""
        self.config = self._load()
        logger.info("Configuration reloaded")
    
    def save(self):
        """Save current configuration to file"""
        save_config_dict(self.config.to_dict(), str(self.config_path))
    
    def update(self, updates: dict):
        """
        Update configuration with new values
        
        Args:
            updates: Dictionary of updates (e.g., {"llm": {"api_key": "xxx"}})
        """
        current = self.config.to_dict()
        
        # Deep merge
        def deep_merge(base: dict, updates: dict) -> dict:
            for key, value in updates.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        merged = deep_merge(current, updates)
        self.config = MilitaryVideoGenConfig(**merged)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like access (for backward compatibility)"""
        return self.config.to_dict().get(key, default)
    
    def validate(self) -> bool:
        """Validate configuration completeness"""
        return self.config.validate_required()
    
    def get_llm_config(self) -> dict:
        """Get LLM configuration as dict"""
        return {
            "api_key": self.config.llm.api_key,
            "base_url": self.config.llm.base_url,
            "model": self.config.llm.model,
        }
    
    def set_llm_config(self, api_key: str, base_url: str, model: str):
        """Set LLM configuration"""
        from military_video_gen.utils.llm_util import normalize_openai_base_url

        self.update({
            "llm": {
                "api_key": api_key,
                "base_url": normalize_openai_base_url(base_url),
                "model": model,
            }
        })
    
    def get_comfyui_config(self) -> dict:
        """Get ComfyUI configuration as dict"""
        return {
            "comfyui_url": self.config.comfyui.comfyui_url,
            "comfyui_api_key": self.config.comfyui.comfyui_api_key,
            "runninghub_api_key": self.config.comfyui.runninghub_api_key,
            "runninghub_concurrent_limit": self.config.comfyui.runninghub_concurrent_limit,
            "runninghub_instance_type": self.config.comfyui.runninghub_instance_type,
            "tts": {
                "default_workflow": self.config.comfyui.tts.default_workflow,
            },
            "image": {
                "default_workflow": self.config.comfyui.image.default_workflow,
                "prompt_prefix": self.config.comfyui.image.prompt_prefix,
            },
            "video": {
                "default_workflow": self.config.comfyui.video.default_workflow,
                "prompt_prefix": self.config.comfyui.video.prompt_prefix,
            }
        }

    def get_api_providers_config(self) -> dict:
        """Get direct API provider configuration as dict"""
        return self.config.api_providers.model_dump()

    def set_api_provider_config(self, provider: str, updates: dict):
        """Set configuration for a direct API provider"""
        self.update({"api_providers": {provider: updates}})
    
    def set_comfyui_config(
        self, 
        comfyui_url: Optional[str] = None,
        comfyui_api_key: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        runninghub_concurrent_limit: Optional[int] = None,
        runninghub_instance_type: Optional[str] = None
    ):
        """Set ComfyUI global configuration"""
        updates = {}
        if comfyui_url is not None:
            updates["comfyui_url"] = comfyui_url
        if comfyui_api_key is not None:
            updates["comfyui_api_key"] = comfyui_api_key
        if runninghub_api_key is not None:
            updates["runninghub_api_key"] = runninghub_api_key
        if runninghub_concurrent_limit is not None:
            updates["runninghub_concurrent_limit"] = runninghub_concurrent_limit
        if runninghub_instance_type is not None:
            # Empty string means disable (treat as None for storage)
            updates["runninghub_instance_type"] = runninghub_instance_type if runninghub_instance_type else None
        
        if updates:
            self.update({"comfyui": updates})
