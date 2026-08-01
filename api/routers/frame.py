"""
Frame/Template rendering endpoints
"""

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.public_paths import to_public_file_url
from api.schemas.frame import FrameRenderRequest, FrameRenderResponse, TemplateParamsResponse
from military_video_gen.services.frame_html import HTMLFrameGenerator
from military_video_gen.utils.media_validation import validate_generated_output
from military_video_gen.utils.safety import redact_path_for_log
from military_video_gen.utils.template_util import parse_template_size, resolve_template_path

router = APIRouter(prefix="/frame", tags=["Frame Rendering"])


@router.post("/render", response_model=FrameRenderResponse)
async def render_frame(
    request: FrameRenderRequest,
    military_video_gen: MilitaryVideoGenDep,
    http_request: Request,
):
    """
    Render a single frame using HTML template
    
    Generates a frame image by combining template, title, text, and image.
    This is useful for previewing templates or generating custom frames.
    
    - **template**: Template key (e.g., '1080x1920/default.html')
    - **title**: Optional title text
    - **text**: Frame text content
    - **image**: Image path (can be local path or URL)
    
    Returns path to generated frame image.
    
    Example:
    ```json
    {
        "template": "1080x1920/modern.html",
        "title": "Welcome",
        "text": "This is a beautiful frame with custom styling",
        "image": "resources/example.png"
    }
    ```
    """
    try:
        logger.info(
            f"Frame render request: template={redact_path_for_log(request.template)}"
        )
        
        # Resolve template path (returns absolute path with "templates/" or "data/templates/" prefix)
        template_path = resolve_template_path(request.template)
        
        # Parse template size
        width, height = parse_template_size(template_path)
        
        # Create HTML frame generator
        generator = HTMLFrameGenerator(template_path)
        
        # Generate frame
        frame_path = await generator.generate_frame(
            title=request.title,
            text=request.text,
            image=request.image
        )
        
        frame_file, _ = validate_generated_output(frame_path, media_kind="image")
        return FrameRenderResponse(
            frame_path=to_public_file_url(http_request, frame_file),
            width=width,
            height=height
        )
        
    except Exception as e:
        raise internal_server_error("Frame render error", e)


@router.get("/template/params", response_model=TemplateParamsResponse)
async def get_template_params(
    template: str
):
    """
    Get custom parameters for a template
    
    Returns the custom parameters defined in the template HTML file.
    These parameters can be passed via `template_params` in video generation requests.
    
    Template parameters are defined using syntax: `{{param_name:type=default}}`
    
    Supported types:
    - `text`: String input
    - `number`: Numeric input
    - `color`: Color picker (hex format)
    - `bool`: Boolean checkbox
    
    Example template syntax:
    ```html
    <div style="color: {{accent_color:color=#ff0000}}">
        {{custom_text:text=Hello World}}
    </div>
    ```
    
    Args:
        template: Template path (e.g., '1080x1920/image_default.html')
    
    Returns:
        Template parameters with their types, defaults, and labels
    
    Example response:
    ```json
    {
        "template": "1080x1920/image_default.html",
        "media_width": 1080,
        "media_height": 1440,
        "params": {
            "accent_color": {
                "type": "color",
                "default": "#ff0000",
                "label": "accent_color"
            },
            "background": {
                "type": "text", 
                "default": "https://example.com/bg.jpg",
                "label": "background"
            }
        }
    }
    ```
    """
    try:
        logger.info(f"Get template params: {redact_path_for_log(template)}")
        
        # Resolve template path
        template_path = resolve_template_path(template)
        
        # Create generator and parse parameters
        generator = HTMLFrameGenerator(template_path)
        params = generator.parse_template_parameters()
        media_width, media_height = generator.get_media_size()
        
        return TemplateParamsResponse(
            template=template,
            media_width=media_width,
            media_height=media_height,
            params=params
        )
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")
    except Exception as e:
        raise internal_server_error("Get template params error", e)

