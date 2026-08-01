"""
HTML-based Frame Generator Service

Renders HTML templates to frame images using Playwright for headless browser rendering.

Linux Environment Requirements:
    - fontconfig package must be installed
    - Basic fonts (e.g., fonts-liberation, fonts-noto) recommended
    
    Ubuntu/Debian: sudo apt-get install -y fontconfig fonts-liberation fonts-noto-cjk
    CentOS/RHEL: sudo yum install -y fontconfig liberation-fonts google-noto-cjk-fonts
    
    Playwright browser install: playwright install --with-deps chromium
"""

import asyncio
import html as html_module
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from loguru import logger

from military_video_gen.utils.safety import redact_path_for_log, sanitize_error_message
from military_video_gen.utils.template_util import parse_template_size


class HTMLFrameGenerator:
    """
    HTML-based frame generator
    
    Renders HTML templates to frame images with variable substitution.
    Uses Playwright for reliable headless browser rendering.
    
    Usage:
        >>> generator = HTMLFrameGenerator("templates/modern.html")
        >>> frame_path = await generator.generate_frame(
        ...     topic="Why reading matters",
        ...     text="Reading builds new neural pathways...",
        ...     image="/path/to/image.png",
        ...     ext={"content_title": "Sample Title", "content_author": "Author Name"}
        ... )
    """
    
    _browser = None
    _playwright = None
    _browser_loop = None
    _browser_lock = None
    _browser_lock_loop = None

    def __init__(self, template_path: str):
        """
        Initialize HTML frame generator
        
        Args:
            template_path: Path to HTML template file (e.g., "templates/1080x1920/default.html")
        """
        self.template_path = template_path
        self.template = self._load_template(template_path)
        
        # Parse video size from template path
        self.width, self.height = parse_template_size(template_path)
        
        self._check_linux_dependencies()
        logger.debug(
            f"Loaded HTML template: {redact_path_for_log(template_path)} "
            f"(size: {self.width}x{self.height})"
        )
    
    
    def _check_linux_dependencies(self):
        """Check Linux system dependencies and warn if missing"""
        if os.name != 'posix':
            return
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['fc-list'], 
                capture_output=True, 
                timeout=2
            )
            
            if result.returncode != 0:
                logger.warning(
                    "fontconfig not found or not working properly. "
                    "Install with: sudo apt-get install -y fontconfig fonts-liberation fonts-noto-cjk"
                )
            elif not result.stdout:
                logger.warning(
                    "No fonts detected by fontconfig. "
                    "Install fonts with: sudo apt-get install -y fonts-liberation fonts-noto-cjk"
                )
            else:
                logger.debug(f"Fontconfig detected {len(result.stdout.splitlines())} fonts")
                
        except FileNotFoundError:
            logger.warning(
                "fontconfig (fc-list) not found on system. "
                "Install with: sudo apt-get install -y fontconfig"
            )
        except Exception as e:
            logger.debug(
                f"Could not check fontconfig status: {sanitize_error_message(e)}"
            )
    
    def _load_template(self, template_path: str) -> str:
        """Load HTML template from file"""
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Template not found: {redact_path_for_log(template_path)}"
            )
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.debug(f"Template loaded: {len(content)} chars")
        return content
    
    def _parse_media_size_from_meta(self) -> tuple[Optional[int], Optional[int]]:
        """
        Parse media size from meta tags in template
        
        Looks for meta tags:
        - <meta name="template:media-width" content="1024">
        - <meta name="template:media-height" content="1024">
        
        Returns:
            Tuple of (width, height) or (None, None) if not found
        """
        from bs4 import BeautifulSoup
        
        try:
            soup = BeautifulSoup(self.template, 'html.parser')
            
            width_meta = soup.find('meta', attrs={'name': 'template:media-width'})
            height_meta = soup.find('meta', attrs={'name': 'template:media-height'})
            
            if width_meta and height_meta:
                width = int(width_meta.get('content', 0))
                height = int(height_meta.get('content', 0))
                
                if width > 0 and height > 0:
                    logger.debug(f"Found media size in meta tags: {width}x{height}")
                    return width, height
            
            return None, None
            
        except Exception as e:
            logger.warning(
                f"Failed to parse media size from meta tags: {sanitize_error_message(e)}"
            )
            return None, None
    
    def get_media_size(self) -> tuple[int, int]:
        """
        Get media size for image/video generation
        
        Returns media size specified in template meta tags.
        
        Returns:
            Tuple of (width, height)
        """
        media_width, media_height = self._parse_media_size_from_meta()
        
        if media_width and media_height:
            return media_width, media_height
        
        logger.warning(
            "No media size meta tags found in template "
            f"{redact_path_for_log(self.template_path)}, using fallback 1024x1024"
        )
        return 1024, 1024
    
    def parse_template_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Parse custom parameters from HTML template
        
        Supports syntax: {{param:type=default}}
        - {{param}} -> text type, no default
        - {{param=value}} -> text type, with default
        - {{param:type}} -> specified type, no default
        - {{param:type=value}} -> specified type, with default
        
        Supported types: text, number, color, bool
        
        Returns:
            Dictionary of custom parameters with their configurations:
            {
                'param_name': {
                    'type': 'text' | 'number' | 'color' | 'bool',
                    'default': Any,
                    'label': str  # same as param_name
                }
            }
        """
        PRESET_PARAMS = {'title', 'text', 'image', 'index'}
        
        PARAM_PATTERN = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?(?:=([^}]+))?\}\}'
        
        params = {}
        
        for match in re.finditer(PARAM_PATTERN, self.template):
            param_name = match.group(1)
            param_type = match.group(2) or 'text'
            default_value = match.group(3)
            
            if param_name in PRESET_PARAMS:
                continue
            
            if param_name in params:
                continue
            
            if param_type not in {'text', 'number', 'color', 'bool'}:
                logger.warning(f"Unknown parameter type '{param_type}' for '{param_name}', defaulting to 'text'")
                param_type = 'text'
            
            parsed_default = self._parse_default_value(param_type, default_value)
            
            params[param_name] = {
                'type': param_type,
                'default': parsed_default,
                'label': param_name,
            }
        
        if params:
            logger.debug(f"Parsed {len(params)} custom parameter(s) from template: {list(params.keys())}")
        
        return params
    
    def _parse_default_value(self, param_type: str, value_str: Optional[str]) -> Any:
        """
        Parse default value based on parameter type
        
        Args:
            param_type: Type of parameter (text, number, color, bool)
            value_str: String value to parse (can be None)
        
        Returns:
            Parsed value with appropriate type
        """
        if value_str is None:
            return {
                'text': '',
                'number': 0,
                'color': '#000000',
                'bool': False,
            }.get(param_type, '')
        
        if param_type == 'number':
            try:
                if '.' in value_str:
                    return float(value_str)
                else:
                    return int(value_str)
            except ValueError:
                logger.warning(f"Invalid number value '{value_str}', using 0")
                return 0
        
        elif param_type == 'bool':
            return value_str.lower() in {'true', '1', 'yes', 'on'}
        
        elif param_type == 'color':
            if value_str.startswith('#'):
                return value_str
            else:
                return f'#{value_str}'
        
        else:  # text
            return value_str
    
    def _replace_parameters(self, html: str, values: Dict[str, Any]) -> str:
        """
        Replace parameter placeholders with actual values
        
        Supports DSL syntax: {{param:type=default}}
        - If value provided in values dict, use it
        - Otherwise, use default value from placeholder
        - If no default, use empty string
        
        Args:
            html: HTML template content
            values: Dictionary of parameter values
        
        Returns:
            HTML with placeholders replaced
        """
        PARAM_PATTERN = r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?(?:=([^}]+))?\}\}'
        
        def replacer(match):
            param_name = match.group(1)
            param_type = match.group(2) or 'text'
            default_value_str = match.group(3)
            
            if param_name in values:
                value = values[param_name]
                if isinstance(value, bool):
                    return 'true' if value else 'false'
                if value is None:
                    return ''
                if param_type == "number":
                    try:
                        return str(float(value))
                    except (TypeError, ValueError):
                        return "0"
                if param_type == "color" and not re.fullmatch(
                    r"#[0-9a-fA-F]{3,8}", str(value)
                ):
                    return "#000000"
                return html_module.escape(str(value), quote=True)
            
            elif default_value_str:
                return html_module.escape(default_value_str, quote=True)
            
            else:
                return ''
        
        return re.sub(PARAM_PATTERN, replacer, html)

    @classmethod
    async def _ensure_browser(cls):
        """Lazily initialize a shared Playwright browser instance"""
        current_loop = asyncio.get_running_loop()
        if cls._browser_lock is None or cls._browser_lock_loop is not current_loop:
            cls._browser_lock = asyncio.Lock()
            cls._browser_lock_loop = current_loop
        async with cls._browser_lock:
            browser_usable = (
                cls._browser is not None
                and cls._browser_loop is current_loop
                and cls._browser.is_connected()
            )
            if not browser_usable:
                if cls._browser is not None and cls._browser_loop is not current_loop:
                    logger.warning(
                        "Detected cross-loop Playwright browser reuse attempt; "
                        "recreating browser for current event loop"
                    )
                cls._browser = None
                cls._playwright = None
                from playwright.async_api import async_playwright

                cls._playwright = await async_playwright().start()
                cls._browser = await cls._playwright.chromium.launch(
                    args=[
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions',
                    ]
                )
                cls._browser_loop = current_loop
                logger.debug("Initialized Playwright Chromium browser")
        return cls._browser

    @classmethod
    def _discard_browser_references(cls):
        """Drop stale Playwright objects that belong to another event loop."""
        cls._browser = None
        cls._playwright = None
        cls._browser_loop = None

    @classmethod
    async def _reset_browser(cls):
        """Best-effort reset for stale or broken Playwright connections."""
        if cls._browser:
            try:
                if cls._browser.is_connected():
                    await asyncio.wait_for(cls._browser.close(), timeout=5)
            except Exception as e:
                logger.debug(
                    "Ignoring error while closing stale browser: "
                    f"{sanitize_error_message(e)}"
                )
            finally:
                cls._browser = None

        if cls._playwright:
            try:
                await asyncio.wait_for(cls._playwright.stop(), timeout=5)
            except Exception as e:
                logger.debug(
                    "Ignoring error while stopping stale Playwright: "
                    f"{sanitize_error_message(e)}"
                )
            finally:
                cls._playwright = None
                cls._browser_loop = None

    @classmethod
    async def close_browser(cls):
        """Shutdown the shared browser instance (call on app teardown)"""
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
            cls._browser_loop = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None
            logger.debug("Playwright browser closed")

    async def generate_frame(
        self,
        title: str,
        text: str,
        image: Optional[str],
        ext: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate frame from HTML template
        
        Video size is automatically determined from template path during initialization.
        
        Args:
            title: Video title
            text: Narration text for this frame
            image: Path to AI-generated image (supports relative path, absolute path, or HTTP URL)
            ext: Additional data (content_title, content_author, etc.)
            output_path: Custom output path (auto-generated if None)
        
        Returns:
            Path to generated frame image
        """
        if image and image.startswith(("http://", "https://")):
            from military_video_gen.research.crawlers.security import URLSafetyChecker

            image = await URLSafetyChecker().validate(image)
        elif image and image.startswith("data:"):
            if not re.match(r"^data:image/(?:png|jpeg|webp|gif);base64,", image, re.I):
                raise ValueError("image data URL must contain a supported base64 image")
            if len(image) > 20 * 1024 * 1024:
                raise ValueError("image data URL exceeds the renderer limit")
        elif image and image.startswith("file://"):
            parsed = urlparse(image)
            image_path = Path(url2pathname(unquote(parsed.path)))
            if parsed.netloc and parsed.netloc not in {"", "localhost"}:
                image_path = Path(f"//{parsed.netloc}/{unquote(parsed.path.lstrip('/'))}")
            image = self._safe_local_image_uri(image_path)
        elif image:
            image_path = Path(image)
            if not image_path.is_absolute():
                image_path = Path.cwd() / image
            image = self._safe_local_image_uri(image_path)
        else:
            image = ""
        
        context = {
            "title": title,
            "text": text,
            "image": image,
            "author": "",
            "brand": "",
            "describe": "",
            "signature": "",
            "hide_branding": True,
        }
        
        if ext:
            context.update(ext)
        
        html = self._replace_parameters(self.template, context)
        if context.get("hide_branding"):
            html = self._hide_branding_elements(html)

        if output_path is None:
            from military_video_gen.utils.os_util import get_output_path
            output_filename = f"frame_{uuid.uuid4().hex[:16]}.png"
            output_path = get_output_path(output_filename)
        else:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        logger.debug(
            f"Rendering HTML template to {redact_path_for_log(output_path)} "
            f"(size: {self.width}x{self.height})"
        )
        tmp_html_path = None
        page = None
        try:
            try:
                browser = await self._ensure_browser()
                page = await browser.new_page(
                    viewport={'width': self.width, 'height': self.height},
                    device_scale_factor=1,
                )
            except Exception as e:
                logger.warning(
                    "Playwright browser connection failed, restarting once: "
                    f"{sanitize_error_message(e)}"
                )
                await self._reset_browser()
                browser = await self._ensure_browser()
                page = await browser.new_page(
                    viewport={'width': self.width, 'height': self.height},
                    device_scale_factor=1,
                )

            from military_video_gen.research.crawlers.security import (
                UnsafeURLError,
                URLSafetyChecker,
            )

            request_checker = URLSafetyChecker()

            async def guard_request(route):
                target = route.request.url
                if target.startswith(("file:", "data:", "about:")):
                    await route.continue_()
                    return
                try:
                    await request_checker.validate(target)
                except (UnsafeURLError, ValueError):
                    await route.abort("blockedbyclient")
                    return
                await route.continue_()

            await page.route("**/*", guard_request)

            try:
                # Write HTML to a temp file and navigate via file:// URL so that
                # local file:// image references are loaded under the same origin.
                fd, tmp_html_path = tempfile.mkstemp(suffix='.html', prefix='pv_frame_')
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(html)
                
                await page.goto(Path(tmp_html_path).as_uri(), wait_until='networkidle')
                await page.screenshot(path=output_path, type='png', omit_background=True)
            finally:
                if page:
                    await page.close()
                if tmp_html_path and os.path.exists(tmp_html_path):
                    os.unlink(tmp_html_path)
            
            logger.info(f"Frame generated: {redact_path_for_log(output_path)}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to render HTML template: {sanitize_error_message(e)}")
            raise RuntimeError(
                "HTML rendering failed: "
                f"{type(e).__name__}: {sanitize_error_message(e)}"
            ) from e

    @staticmethod
    def _safe_local_image_uri(image_path: Path) -> str:
        """Allow local renderer images only from project media/resource roots."""
        from military_video_gen.utils.os_util import get_root_path

        candidate = image_path.resolve()
        roots = [
            Path(get_root_path(name)).resolve()
            for name in ("output", "temp", "data", "templates")
        ]
        if not candidate.is_file() or not any(
            candidate == root or root in candidate.parents for root in roots
        ):
            raise ValueError("local renderer image is outside allowed project roots")
        return candidate.as_uri()

    def _hide_branding_elements(self, html: str) -> str:
        """Hide default template branding such as @MilitaryVideoGen footers."""
        css = """
        <style id="military-video-gen-hide-branding">
            .author-section,
            .author,
            .author-desc,
            .logo-section,
            .signature {
                display: none !important;
            }
        </style>
        """
        if "</head>" in html:
            return html.replace("</head>", f"{css}</head>", 1)
        return css + html
