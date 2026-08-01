"""
Workflow Path Resolver

Standardized workflow path resolution for all ComfyUI services.
Convention: {source}/{service}.json

Examples:
    - Image analysis: selfhost/analyse_image.json, runninghub/analyse_image.json
    - Image generation: selfhost/image.json, runninghub/image.json
    - Video generation: selfhost/video.json, runninghub/video.json
    - TTS: selfhost/tts.json, runninghub/tts.json
"""

from typing import Literal

WorkflowSource = Literal['runninghub', 'selfhost']


def resolve_workflow_path(
    service_name: str,
    source: WorkflowSource = 'runninghub'
) -> str:
    """
    Resolve workflow path using standardized naming convention
    
    Convention: workflows/{source}/{service_name}.json
    
    Args:
        service_name: Service identifier (e.g., "analyse_image", "image", "video", "tts")
        source: Workflow source - 'runninghub' (default) or 'selfhost'
    
    Returns:
        Workflow path in format: "{source}/{service_name}.json"
        
    Examples:
        >>> resolve_workflow_path("analyse_image", "runninghub")
        'runninghub/analyse_image.json'
        
        >>> resolve_workflow_path("analyse_image", "selfhost")
        'selfhost/analyse_image.json'
        
        >>> resolve_workflow_path("image")  # defaults to runninghub
        'runninghub/image.json'
    """
    return f"{source}/{service_name}.json"


def get_default_source() -> WorkflowSource:
    """
    Get default workflow source
    
    Returns:
        'runninghub' - Cloud-first approach, better for beginners
    """
    return 'runninghub'
