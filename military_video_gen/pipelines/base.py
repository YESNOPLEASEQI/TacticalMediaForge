"""
Base Pipeline for Video Generation

All custom pipelines should inherit from BasePipeline.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

from loguru import logger

from military_video_gen.models.progress import ProgressEvent
from military_video_gen.models.storyboard import VideoGenerationResult


class BasePipeline(ABC):
    """
    Base pipeline for video generation
    
    All custom pipelines should inherit from this class and implement __call__.
    
    Design principles:
    - Each pipeline represents a complete video generation workflow
    - Pipelines are independent and can have completely different logic
    - Pipelines have access to all core services via self.core
    - Pipelines should report progress via progress_callback
    
    Example:
        >>> class MyPipeline(BasePipeline):
        ...     async def __call__(self, text: str, **kwargs):
        ...         # Step 1: Generate content
        ...         narrations = await some_logic(text)
        ...         
        ...         # Step 2: Process frames
        ...         for narration in narrations:
        ...             audio = await self.core.tts(narration)
        ...             # ...
        ...         
        ...         return VideoGenerationResult(...)
    """
    
    def __init__(self, military_video_gen_core):
        """
        Initialize pipeline with core services
        
        Args:
            military_video_gen_core: MilitaryVideoGenCore instance (provides access to all services)
        """
        self.core = military_video_gen_core
        
        # Quick access to services (convenience)
        self.llm = military_video_gen_core.llm
        self.tts = military_video_gen_core.tts
        self.media = military_video_gen_core.media
        self.video = military_video_gen_core.video
        
        # Backward compatibility alias
        self.image = military_video_gen_core.media
    
    @abstractmethod
    async def __call__(
        self,
        text: str,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        **kwargs
    ) -> VideoGenerationResult:
        """
        Execute the pipeline
        
        Args:
            text: Input text (meaning varies by pipeline)
            progress_callback: Optional callback for progress updates (receives ProgressEvent)
            **kwargs: Pipeline-specific parameters
            
        Returns:
            VideoGenerationResult with video path and metadata
            
        Raises:
            Exception: Pipeline-specific exceptions
        """
        pass
    
    def _report_progress(
        self,
        callback: Optional[Callable[[ProgressEvent], None]],
        event_type: str,
        progress: float,
        **kwargs
    ):
        """
        Report progress via callback
        
        Args:
            callback: Progress callback function
            event_type: Type of progress event
            progress: Progress value (0.0-1.0)
            **kwargs: Additional event-specific parameters (frame_current, frame_total, etc.)
        """
        if callback:
            event = ProgressEvent(event_type=event_type, progress=progress, **kwargs)
            callback(event)
            logger.debug(f"Progress: {progress*100:.0f}% - {event_type}")
        else:
            logger.debug(f"Progress: {progress*100:.0f}% - {event_type}")

