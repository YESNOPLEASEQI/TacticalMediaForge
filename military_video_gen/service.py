"""
MilitaryVideoGen Core - Service Layer

Provides unified access to all capabilities (LLM, TTS, Image, etc.)
"""

import hashlib
import json
from typing import Optional

from comfykit import ComfyKit
from loguru import logger

from military_video_gen.config import config_manager
from military_video_gen.pipelines.asset_based import AssetBasedPipeline
from military_video_gen.pipelines.custom import CustomPipeline
from military_video_gen.pipelines.standard import StandardPipeline
from military_video_gen.services.api_asset_analysis import APIAssetAnalysisService
from military_video_gen.services.api_media import APIProviderMediaService
from military_video_gen.services.frame_processor import FrameProcessor
from military_video_gen.services.history_manager import HistoryManager
from military_video_gen.services.image_analysis import ImageAnalysisService
from military_video_gen.services.llm_service import LLMService
from military_video_gen.services.media import MediaService
from military_video_gen.services.persistence import PersistenceService
from military_video_gen.services.tts_service import TTSService
from military_video_gen.services.video import VideoService
from military_video_gen.services.video_analysis import VideoAnalysisService
from military_video_gen.utils.safety import redact_url_for_log, sanitize_error_message


class MilitaryVideoGenCore:
    """
    MilitaryVideoGen Core - Service Layer
    
    Provides unified access to all capabilities.
    
    Usage:
        from military_video_gen import military_video_gen
        
        # Initialize
        await military_video_gen.initialize()
        
        # Use capabilities directly
        answer = await military_video_gen.llm("Explain atomic habits")
        audio = await military_video_gen.tts("Hello world")
        media = await military_video_gen.media(prompt="a cat")
        
        # Check active capabilities
        print(f"Using LLM: {military_video_gen.llm.active}")
        print(f"Available TTS: {military_video_gen.tts.available}")
    
    Architecture (Simplified):
        MilitaryVideoGenCore (this class)
          ├── config (configuration)
          ├── llm (LLM service - direct OpenAI SDK)
          ├── tts (TTS service - ComfyKit workflows)
          ├── media (Media service - ComfyKit workflows, supports image & video)
          └── pipelines (video generation pipelines)
              ├── standard (standard workflow)
              ├── custom (custom workflow template)
              └── ... (extensible)
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize MilitaryVideoGen Core
        
        Args:
            config_path: Path to configuration file
        """
        # Use global config manager singleton
        self.config = config_manager.config.to_dict()
        self._initialized = False
        
        # ComfyKit lazy initialization (created on first use, recreated on config change)
        self._comfykit: Optional[ComfyKit] = None
        self._comfykit_config_hash: Optional[str] = None
        self._comfykit_overrides: dict[str, ComfyKit] = {}
        
        # Core services (initialized in initialize())
        self.llm: Optional[LLMService] = None
        self.tts: Optional[TTSService] = None
        self.media: Optional[MediaService] = None
        self.api_media: Optional[APIProviderMediaService] = None
        self.video: Optional[VideoService] = None
        self.frame_processor: Optional[FrameProcessor] = None
        self.persistence: Optional[PersistenceService] = None
        self.history: Optional[HistoryManager] = None
        
        # Video generation pipelines (dictionary of pipeline_name -> pipeline_instance)
        self.pipelines = {}
        
        # Default pipeline callable (for backward compatibility)
        self.generate_video = None
    
    def _get_comfykit_config(self, comfyui_url: Optional[str] = None) -> dict:
        """
        Get current ComfyKit configuration from config_manager
        
        Returns:
            ComfyKit configuration dict
        """
        # Reload config from global config_manager (to support hot reload)
        self.config = config_manager.config.to_dict()
        
        comfyui_config = self.config.get("comfyui", {})
        # RunningHub's dependency-level retry loop retries POST task creation,
        # which is billable and non-idempotent. Disable it at the integration
        # boundary; polling resilience can be handled separately.
        kit_config = {
            "runninghub_retry_count": 0,
            # The dependency otherwise polls forever. Keep this below the
            # API's default one-hour task deadline so deferred cancellation
            # always reaches a terminal state.
            "runninghub_timeout": 1800,
        }
        
        if comfyui_config.get("comfyui_url"):
            kit_config["comfyui_url"] = comfyui_config["comfyui_url"]
        if comfyui_url:
            kit_config["comfyui_url"] = comfyui_url
        if comfyui_config.get("comfyui_api_key"):
            kit_config["api_key"] = comfyui_config["comfyui_api_key"]
        if comfyui_config.get("runninghub_api_key"):
            kit_config["runninghub_api_key"] = comfyui_config["runninghub_api_key"]
        # Only pass instance_type if it has a non-empty value
        instance_type = comfyui_config.get("runninghub_instance_type")
        if instance_type and instance_type.strip():
            kit_config["runninghub_instance_type"] = instance_type
        
        return kit_config
    
    def _compute_comfykit_config_hash(self, config: dict) -> str:
        """
        Compute hash of ComfyKit configuration for change detection
        
        Args:
            config: ComfyKit configuration dict
        
        Returns:
            MD5 hash of config
        """
        # Sort keys for consistent hash
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    async def _get_or_create_comfykit(self, comfyui_url: Optional[str] = None) -> ComfyKit:
        """
        Get or create ComfyKit instance (lazy initialization with config change detection)
        
        This method:
        1. Creates ComfyKit on first use (lazy initialization)
        2. Detects configuration changes and recreates instance if needed
        3. Ensures proper cleanup of old instances
        
        Returns:
            ComfyKit instance
        """
        current_config = self._get_comfykit_config(comfyui_url=comfyui_url)
        current_hash = self._compute_comfykit_config_hash(current_config)

        if comfyui_url:
            kit = self._comfykit_overrides.get(current_hash)
            if kit is None:
                logger.info(
                    "Creating dedicated ComfyKit instance for endpoint {}",
                    redact_url_for_log(comfyui_url),
                )
                kit = ComfyKit(**current_config)
                self._comfykit_overrides[current_hash] = kit
            return kit
        
        # Check if we need to create or recreate ComfyKit
        if self._comfykit is None or self._comfykit_config_hash != current_hash:
            # Close old instance if exists
            if self._comfykit is not None:
                logger.info("🔄 ComfyUI configuration changed, recreating ComfyKit instance...")
                try:
                    await self._comfykit.close()
                except Exception as e:
                    logger.warning(
                        "Failed to close old ComfyKit instance: "
                        f"{sanitize_error_message(e)}"
                    )
                self._comfykit = None
            
            # Create new instance with current config
            logger.info("✨ Creating ComfyKit instance...")
            logger.debug(
                "ComfyKit configured: source={}, url_configured={}, api_key_configured={}, "
                "runninghub_key_configured={}",
                current_config.get("source"),
                bool(current_config.get("comfyui_url")),
                bool(current_config.get("api_key")),
                bool(current_config.get("runninghub_api_key")),
            )
            self._comfykit = ComfyKit(**current_config)
            self._comfykit_config_hash = current_hash
            logger.info("✅ ComfyKit instance created")
        
        return self._comfykit
    
    async def initialize(self):
        """
        Initialize core capabilities
        
        This initializes all services and must be called before using any capabilities.
        Note: ComfyKit is NOT initialized here - it's lazily initialized on first use.
        
        Example:
            await military_video_gen.initialize()
        """
        if self._initialized:
            logger.warning("MilitaryVideoGen already initialized")
            return
        
        logger.info("🚀 Initializing MilitaryVideoGen...")
        
        # 1. Initialize core services (ComfyKit will be lazy-loaded later)
        # Initialize services
        self.llm = LLMService(self.config)
        self.tts = TTSService(self.config, core=self)
        self.api_media = APIProviderMediaService(self.config, core=self)
        self.media = MediaService(self.config, core=self)
        self.image = self.media  # Alias for backward compatibility
        self.image_analysis = ImageAnalysisService(self.config, core=self)
        self.video_analysis = VideoAnalysisService(self.config, core=self)
        self.api_asset_analysis = APIAssetAnalysisService(self.config, core=self)
        self.video = VideoService()
        self.frame_processor = FrameProcessor(self)
        self.persistence = PersistenceService(output_dir="output")
        self.history = HistoryManager(self.persistence)
        
        # 2. Register video generation pipelines
        self.pipelines = {
            "standard": StandardPipeline(self),
            "custom": CustomPipeline(self),
            "asset_based": AssetBasedPipeline(self),
        }
        logger.info(f"📹 Registered pipelines: {', '.join(self.pipelines.keys())}")
        
        # 3. Set default pipeline callable (for backward compatibility)
        self.generate_video = self._create_generate_video_wrapper()
        
        self._initialized = True
        logger.info("✅ MilitaryVideoGen initialized successfully\n")
    
    async def cleanup(self):
        """
        Cleanup resources (close ComfyKit session)
        
        Example:
            await military_video_gen.cleanup()
        """
        if self._comfykit:
            logger.info("🧹 Closing ComfyKit session...")
            try:
                await self._comfykit.close()
                logger.info("✅ ComfyKit session closed")
            except Exception as e:
                logger.error(f"Failed to close ComfyKit: {sanitize_error_message(e)}")
            finally:
                self._comfykit = None
                self._comfykit_config_hash = None
        for kit in self._comfykit_overrides.values():
            try:
                await kit.close()
            except Exception as e:
                logger.warning(f"Failed to close dedicated ComfyKit: {sanitize_error_message(e)}")
        self._comfykit_overrides.clear()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
    
    def _create_generate_video_wrapper(self):
        """
        Create a wrapper function for generate_video that supports pipeline selection
        
        This maintains backward compatibility while adding pipeline support.
        """
        async def generate_video_wrapper(
            text: str,
            pipeline: str = "standard",
            **kwargs
        ):
            """
            Generate video using specified pipeline
            
            Args:
                text: Input text
                pipeline: Pipeline name ("standard", "book_summary", etc.)
                **kwargs: Pipeline-specific parameters
            
            Returns:
                VideoGenerationResult
            
            Examples:
                # Use standard pipeline (default)
                result = await military_video_gen.generate_video(
                    text="如何提高学习效率",
                    n_scenes=5
                )
                
                # Use custom pipeline
                result = await military_video_gen.generate_video(
                    text=your_content,
                    pipeline="custom",
                    custom_param_example="custom_value"
                )
            """
            if pipeline not in self.pipelines:
                available = ", ".join(self.pipelines.keys())
                raise ValueError(
                    f"Unknown pipeline: '{pipeline}'. "
                    f"Available pipelines: {available}"
                )
            
            # Pipeline objects contain callbacks and, for asset-based jobs,
            # per-run counters.  A fresh instance prevents concurrent tasks
            # from contaminating one another through singleton state.
            pipeline_instance = type(self.pipelines[pipeline])(self)
            return await pipeline_instance(text=text, **kwargs)
        
        return generate_video_wrapper
    
    @property
    def project_name(self) -> str:
        """Get project name from config"""
        return self.config.get("project_name", "MilitaryVideoGen")
    
    def __repr__(self) -> str:
        """String representation"""
        status = "initialized" if self._initialized else "not initialized"
        pipelines = f"pipelines={list(self.pipelines.keys())}" if self._initialized else ""
        return f"<MilitaryVideoGenCore project={self.project_name!r} status={status} {pipelines}>"


# Global instance
military_video_gen = MilitaryVideoGenCore()
