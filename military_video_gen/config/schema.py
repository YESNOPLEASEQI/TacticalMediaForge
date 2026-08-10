"""
Configuration schema with Pydantic models

Single source of truth for all configuration defaults and validation.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM configuration"""

    api_key: str = Field(default="", description="LLM API Key")
    base_url: str = Field(default="", description="LLM API Base URL")
    model: str = Field(default="", description="LLM Model Name")


class APIProviderCommonConfig(BaseModel):
    """Common API provider settings"""

    print_model_input: bool = Field(
        default=False, description="Print provider request parameters for debugging"
    )
    local_proxy: str = Field(default="", description="Local HTTP proxy for providers that need it")


class APIKeyProviderConfig(BaseModel):
    """Provider settings with API key and optional base URL"""

    api_key: str = Field(default="", description="Provider API Key")
    base_url: str = Field(default="", description="Provider API Base URL")
    use_proxy: bool = Field(
        default=False, description="Route provider requests through common local proxy"
    )


class AccessSecretProviderConfig(BaseModel):
    """Provider settings with access key / secret key credentials"""

    base_url: str = Field(default="", description="Provider API Base URL")
    access_key: str = Field(default="", description="Provider Access Key")
    secret_key: str = Field(default="", description="Provider Secret Key")
    use_proxy: bool = Field(
        default=False, description="Route provider requests through common local proxy"
    )


class APIProvidersConfig(BaseModel):
    """Direct model provider API configuration"""

    common: APIProviderCommonConfig = Field(default_factory=APIProviderCommonConfig)
    openai: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    dashscope: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    deepseek: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    gemini: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    ark: APIKeyProviderConfig = Field(default_factory=APIKeyProviderConfig)
    kling: AccessSecretProviderConfig = Field(default_factory=AccessSecretProviderConfig)


class TTSLocalConfig(BaseModel):
    """Local TTS configuration (Edge TTS)"""

    voice: str = Field(default="zh-CN-YunjianNeural", description="Edge TTS voice ID")
    speed: float = Field(
        default=1.2, ge=0.5, le=2.0, description="Speech speed multiplier (0.5-2.0)"
    )


class TTSComfyUIConfig(BaseModel):
    """ComfyUI TTS configuration"""

    default_workflow: Optional[str] = Field(
        default=None, description="Default TTS workflow (optional)"
    )


class TTSSubConfig(BaseModel):
    """TTS-specific configuration (under comfyui.tts)"""

    inference_mode: str = Field(
        default="local", description="TTS inference mode: 'local' or 'comfyui'"
    )
    local: TTSLocalConfig = Field(
        default_factory=TTSLocalConfig, description="Local TTS (Edge TTS) configuration"
    )
    comfyui: TTSComfyUIConfig = Field(
        default_factory=TTSComfyUIConfig, description="ComfyUI TTS configuration"
    )

    # Backward compatibility: keep default_workflow at top level
    @property
    def default_workflow(self) -> Optional[str]:
        """Get default workflow (for backward compatibility)"""
        return self.comfyui.default_workflow


class ImageSubConfig(BaseModel):
    """Image-specific configuration (under comfyui.image)"""

    default_workflow: Optional[str] = Field(
        default=None, description="Default image workflow (optional)"
    )
    prompt_prefix: str = Field(
        default="Minimalist black-and-white matchstick figure style illustration, clean lines, simple sketch style",
        description="Prompt prefix for all image generation",
    )


class VideoSubConfig(BaseModel):
    """Video-specific configuration (under comfyui.video)"""

    default_workflow: Optional[str] = Field(
        default=None, description="Default video workflow (optional)"
    )
    prompt_prefix: str = Field(
        default="Photorealistic military documentary footage, authentic real-world materials and scale, natural lighting, neutral color grading, physically plausible motion, restrained observational camera work",
        description="Prompt prefix for all video generation",
    )


class H3ReferenceConfig(BaseModel):
    """MiniMax H3 reference-to-video configuration."""

    enabled: bool = Field(default=True, description="Enable MiniMax H3 reference shots")
    comfyui_url: str = Field(
        default="",
        description="Optional dedicated ComfyUI endpoint; empty uses the global endpoint",
    )
    workflow: str = Field(
        default="selfhost/video_minimax_h3_reference.json",
        description="API-format ComfyUI workflow based on MiniMaxH3ReferenceToVideo",
    )
    max_reference_images: int = Field(default=4, ge=1, le=9)
    diffusion_model: str = Field(
        default="",
        description="Optional H3 diffusion model filename override for the target ComfyUI installation",
    )
    text_encoder: str = Field(
        default="",
        description="Optional H3 text encoder filename override for the target ComfyUI installation",
    )
    width: int = Field(
        default=1344,
        ge=256,
        description="H3 generation width; kept independent from the composition template size",
    )
    height: int = Field(
        default=768,
        ge=256,
        description="H3 generation height; kept independent from the composition template size",
    )


class ComfyUIConfig(BaseModel):
    """ComfyUI configuration (includes global settings and service-specific configs)"""

    comfyui_url: str = Field(default="http://127.0.0.1:8188", description="ComfyUI Server URL")
    comfyui_api_key: Optional[str] = Field(default=None, description="ComfyUI API Key (optional)")
    runninghub_api_key: Optional[str] = Field(
        default=None, description="RunningHub API Key (optional)"
    )
    runninghub_concurrent_limit: int = Field(
        default=1, ge=1, le=10, description="RunningHub concurrent execution limit (1-10)"
    )
    runninghub_instance_type: Optional[str] = Field(
        default=None, description="RunningHub instance type (optional, set to 'plus' for 48GB VRAM)"
    )
    tts: TTSSubConfig = Field(
        default_factory=TTSSubConfig, description="TTS-specific configuration"
    )
    image: ImageSubConfig = Field(
        default_factory=ImageSubConfig, description="Image-specific configuration"
    )
    video: VideoSubConfig = Field(
        default_factory=VideoSubConfig, description="Video-specific configuration"
    )
    h3_reference: H3ReferenceConfig = Field(
        default_factory=H3ReferenceConfig,
        description="MiniMax H3 visual reference configuration",
    )


class TemplateConfig(BaseModel):
    """Template configuration"""

    default_template: str = Field(
        default="1080x1920/default.html", description="Default frame template path"
    )


class ResearchSearchConfig(BaseModel):
    """SearXNG-backed research search limits."""

    provider: Literal["searxng"] = "searxng"
    base_url: str = "http://searxng:8080"
    engines: list[str] = Field(
        default_factory=lambda: ["baidu", "360search", "sogou"],
        min_length=1,
        description="Direct-reachable SearXNG engines used for research queries",
    )
    max_queries: int = Field(default=5, ge=1, le=5)
    max_results_per_query: int = Field(default=5, ge=1)
    max_pages: int = Field(default=8, ge=1)
    max_pages_per_domain: int = Field(default=2, ge=1)
    max_rounds: int = Field(default=2, ge=1, le=2)
    timeout_seconds: float = Field(default=20, gt=0)


class ResearchCrawlConfig(BaseModel):
    """Crawl4AI limits and the name of its runtime token variable."""

    provider: Literal["crawl4ai"] = "crawl4ai"
    base_url: str = "http://crawl4ai:11235"
    auth_token_env: str = "CRAWL4AI_API_TOKEN"
    global_concurrency: int = Field(default=2, ge=1)
    per_domain_concurrency: int = Field(default=1, ge=1)
    connect_timeout_seconds: float = Field(default=10, gt=0)
    request_timeout_seconds: float = Field(default=75, gt=0)
    page_timeout_seconds: float = Field(default=30, gt=0)
    max_redirects: int = Field(default=5, ge=0)
    max_html_bytes: int = Field(default=5_242_880, ge=1)
    max_pdf_bytes: int = Field(default=20_971_520, ge=1)
    cache_ttl_hours: int = Field(default=24, ge=0)
    official_cache_ttl_hours: int = Field(default=168, ge=0)
    failed_cache_ttl_minutes: int = Field(default=15, ge=0)
    respect_robots_txt: bool = False
    allow_proxy_fake_ip: bool = False


class ResearchVerificationConfig(BaseModel):
    """Evidence and orchestration thresholds."""

    minimum_verified_claim_confidence: float = Field(default=0.75, ge=0, le=1)
    minimum_low_confidence_claim_confidence: float = Field(default=0.65, ge=0, le=1)
    minimum_discovery_claim_confidence: float = Field(default=0.55, ge=0, le=1)
    minimum_visual_fact_confidence: float = Field(default=0.65, ge=0, le=1)
    structured_model: str | None = None
    total_timeout_seconds: float = Field(default=120, gt=0)
    extraction_timeout_seconds: float = Field(default=45, gt=0)
    planning_timeout_seconds: float = Field(default=30, gt=0)


class ResearchConfig(BaseModel):
    """Evidence-grounded storyboard research configuration."""

    enabled: bool = False
    default_mode: Literal["verified"] = "verified"
    search: ResearchSearchConfig = Field(default_factory=ResearchSearchConfig)
    crawl: ResearchCrawlConfig = Field(default_factory=ResearchCrawlConfig)
    verification: ResearchVerificationConfig = Field(default_factory=ResearchVerificationConfig)


class MilitaryVideoGenConfig(BaseModel):
    """MilitaryVideoGen main configuration"""

    project_name: str = Field(default="MilitaryVideoGen", description="Project name")
    llm: LLMConfig = Field(default_factory=LLMConfig)
    api_providers: APIProvidersConfig = Field(default_factory=APIProvidersConfig)
    comfyui: ComfyUIConfig = Field(default_factory=ComfyUIConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)

    def is_llm_configured(self) -> bool:
        """Check if LLM is properly configured"""
        return bool(
            self.llm.api_key
            and self.llm.api_key.strip()
            and self.llm.base_url
            and self.llm.base_url.strip()
            and self.llm.model
            and self.llm.model.strip()
        )

    def validate_required(self) -> bool:
        """Validate required configuration"""
        return self.is_llm_configured()

    def to_dict(self) -> dict:
        """Convert to dictionary (for backward compatibility)"""
        return self.model_dump()
