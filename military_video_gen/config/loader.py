"""
Configuration loader - Pure YAML

Handles loading and saving configuration from/to YAML files.
"""
import os
import re
from pathlib import Path

import yaml
from loguru import logger

from military_video_gen.utils.safety import redact_path_for_log, sanitize_error_message

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _expand_environment(value, *, key: str | None = None):
    """Recursively expand ${VAR:-default}, excluding token-variable names."""
    if isinstance(value, dict):
        return {
            item_key: _expand_environment(item, key=item_key)
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_expand_environment(item, key=key) for item in value]
    if not isinstance(value, str) or key == "auth_token_env":
        return value

    def replace(match: re.Match[str]) -> str:
        variable, default = match.groups()
        return os.environ.get(variable, default if default is not None else match.group(0))

    return _ENV_PATTERN.sub(replace, value)


def load_config_dict(config_path: str = "config.yaml") -> dict:
    """
    Load configuration from YAML file
    
    Args:
        config_path: Path to config file
        
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        logger.warning(f"Config file not found: {redact_path_for_log(config_path)}")
        logger.info("Using default configuration")
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = _expand_environment(yaml.safe_load(f) or {})
        logger.info(f"Configuration loaded from {redact_path_for_log(config_path)}")
        return data
    except Exception as e:
        logger.error(f"Failed to load config: {sanitize_error_message(e)}")
        return {}


def save_config_dict(config: dict, config_path: str = "config.yaml"):
    """
    Save configuration to YAML file
    
    Args:
        config: Configuration dictionary
        config_path: Path to config file
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"Configuration saved to {redact_path_for_log(config_path)}")
    except Exception as e:
        logger.error(f"Failed to save config: {sanitize_error_message(e)}")
        raise

