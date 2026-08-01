"""
File service endpoints

Provides access to generated files (videos, images, audio) and resource files.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.errors import internal_server_error
from military_video_gen.utils.os_util import get_root_path
from military_video_gen.utils.safety import redact_path_for_log

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/{file_path:path}")
async def get_file(file_path: str):
    """
    Get file by path
    
    Serves files from allowed directories:
    - output/ - Generated files (videos, images, audio)
    - workflows/ - ComfyUI workflow files
    - templates/ - HTML templates
    - bgm/ - Background music
    - data/bgm/ - Custom background music
    - data/templates/ - Custom templates
    - resources/ - Other resources (images, fonts, etc.)
    
    - **file_path**: File path relative to allowed directories
    
    Examples:
    - "abc123.mp4" → output/abc123.mp4
    - "workflows/runninghub/image_flux.json" → workflows/runninghub/image_flux.json
    - "templates/1080x1920/default.html" → templates/1080x1920/default.html
    - "bgm/default.mp3" → bgm/default.mp3
    - "resources/example.png" → resources/example.png
    
    Returns file for download or preview.
    """
    try:
        # Define allowed directories (in priority order)
        allowed_prefixes = [
            "output/",
            "workflows/",
            "templates/",
            "bgm/",
            "data/bgm/",
            "data/templates/",
            "resources/",
        ]
        
        # Check if path starts with allowed prefix, otherwise try output/
        full_path = None
        for prefix in allowed_prefixes:
            if file_path.startswith(prefix):
                full_path = file_path
                break
        
        # If no prefix matched, assume it's in output/ (backward compatibility)
        if full_path is None:
            full_path = f"output/{file_path}"
        
        project_root = Path(get_root_path()).resolve()
        abs_path = (project_root / full_path).resolve()

        allowed_roots = [
            (project_root / prefix.rstrip("/")).resolve()
            for prefix in allowed_prefixes
        ]
        if not any(abs_path.is_relative_to(root) for root in allowed_roots):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not abs_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {redact_path_for_log(file_path)}",
            )
        
        if not abs_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"Path is not a file: {redact_path_for_log(file_path)}",
            )
        
        # Determine media type
        suffix = abs_path.suffix.lower()
        media_types = {
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.html': 'text/html',
            '.json': 'application/json',
        }
        media_type = media_types.get(suffix, 'application/octet-stream')
        
        # Use inline disposition for browser preview
        return FileResponse(
            path=str(abs_path),
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{abs_path.name}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise internal_server_error("File access error", e)

