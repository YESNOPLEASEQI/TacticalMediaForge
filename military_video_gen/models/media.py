"""
Media generation result models
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MediaResult(BaseModel):
    """
    Media generation result from workflow execution
    
    Supports both image and video outputs from ComfyUI workflows.
    The media_type indicates what kind of media was generated.
    
    Attributes:
        media_type: Type of media generated ("image" or "video")
        url: URL or path to the generated media
        duration: Duration in seconds (only for video, None for image)
    
    Examples:
        # Image result
        MediaResult(media_type="image", url="http://example.com/image.png")
        
        # Video result
        MediaResult(media_type="video", url="http://example.com/video.mp4", duration=5.2)
    """
    
    media_type: Literal["image", "video"] = Field(
        description="Type of generated media"
    )
    url: str = Field(
        description="URL or path to the generated media file"
    )
    duration: Optional[float] = Field(
        None,
        description="Duration in seconds (only applicable for video)"
    )
    
    @property
    def is_image(self) -> bool:
        """Check if this is an image result"""
        return self.media_type == "image"
    
    @property
    def is_video(self) -> bool:
        """Check if this is a video result"""
        return self.media_type == "video"

