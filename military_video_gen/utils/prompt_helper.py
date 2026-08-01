"""
Prompt helper utilities

Simple utilities for building prompts with optional prefixes.
"""


def build_image_prompt(prompt: str, prefix: str = "") -> str:
    """
    Build final image prompt with optional prefix
    
    Args:
        prompt: User's raw prompt
        prefix: Optional prefix to add before the prompt
    
    Returns:
        Final prompt with prefix applied (if provided)
    
    Examples:
        >>> build_image_prompt("a cat", "")
        'a cat'
        
        >>> build_image_prompt("a cat", "anime style")
        'anime style, a cat'
        
        >>> build_image_prompt("a cat", "  anime style  ")
        'anime style, a cat'
    """
    prefix = prefix.strip() if prefix else ""
    prompt = prompt.strip() if prompt else ""
    
    if prefix and prompt:
        return f"{prefix}, {prompt}"
    elif prefix:
        return prefix
    else:
        return prompt

