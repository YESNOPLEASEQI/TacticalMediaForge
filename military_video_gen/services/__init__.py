"""
MilitaryVideoGen Services

Core services providing atomic capabilities.

Services:
- LLMService: LLM text generation
- TTSService: Text-to-speech
- MediaService: Media generation (image & video)
- VideoService: Video processing
- FrameProcessor: Frame processing orchestrator
- PersistenceService: Task metadata and storyboard persistence
- HistoryManager: History management business logic
- ComfyBaseService: Base class for ComfyUI-based services
"""

from military_video_gen.services.comfy_base_service import ComfyBaseService
from military_video_gen.services.frame_processor import FrameProcessor
from military_video_gen.services.history_manager import HistoryManager
from military_video_gen.services.llm_service import LLMService
from military_video_gen.services.media import MediaService
from military_video_gen.services.persistence import PersistenceService
from military_video_gen.services.tts_service import TTSService
from military_video_gen.services.video import VideoService

# Backward compatibility alias
ImageService = MediaService

__all__ = [
    "ComfyBaseService",
    "LLMService",
    "TTSService",
    "MediaService",
    "ImageService",  # Backward compatibility
    "VideoService",
    "FrameProcessor",
    "PersistenceService",
    "HistoryManager",
]

