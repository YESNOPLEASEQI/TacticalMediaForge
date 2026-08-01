"""
Video Analysis Service - ComfyUI Workflow-based implementation

Uses ComfyUI workflows to analyze video content and generate descriptions.
"""

from pathlib import Path
from typing import Literal, Optional

from loguru import logger

from military_video_gen.services.comfy_base_service import ComfyBaseService
from military_video_gen.utils.async_utils import run_async_until_stopped
from military_video_gen.utils.safety import redact_path_for_log, sanitize_error_message


class VideoAnalysisService(ComfyBaseService):
    """
    Video analysis service - Workflow-based
    
    Uses ComfyKit to execute video understanding workflows.
    Returns detailed textual descriptions of video content.
    
    Convention: workflows follow {source}/analyse_video.json pattern
    - runninghub/analyse_video.json (default, cloud-based)
    - selfhost/analyse_video.json (local ComfyUI, future)
    
    Usage:
        # Use default (runninghub cloud)
        description = await military_video_gen.video_analysis("path/to/video.mp4")
        
        # Use local ComfyUI (future)
        description = await military_video_gen.video_analysis(
            "path/to/video.mp4",
            source="selfhost"
        )
        
        # List available workflows
        workflows = military_video_gen.video_analysis.list_workflows()
    """
    
    WORKFLOW_PREFIX = "analyse_video"
    WORKFLOWS_DIR = "workflows"
    
    def __init__(self, config: dict, core=None):
        """
        Initialize video analysis service
        
        Args:
            config: Full application config dict
            core: MilitaryVideoGenCore instance (for accessing shared ComfyKit)
        """
        super().__init__(config, service_name="video_analysis", core=core)
    
    async def __call__(
        self,
        video_path: str,
        # Workflow source selection
        source: Literal['runninghub', 'selfhost'] = 'runninghub',
        workflow: Optional[str] = None,
        # ComfyUI connection (optional overrides)
        comfyui_url: Optional[str] = None,
        runninghub_api_key: Optional[str] = None,
        # Additional workflow parameters
        **params
    ) -> str:
        """
        Analyze a video using workflow
        
        Args:
            video_path: Path to the video file (local or URL)
            source: Workflow source - 'runninghub' (cloud, default) or 'selfhost' (local ComfyUI)
            workflow: Workflow filename (optional, overrides source-based resolution)
            comfyui_url: ComfyUI URL (optional, overrides config)
            runninghub_api_key: RunningHub API key (optional, overrides config)
            **params: Additional workflow parameters
        
        Returns:
            str: Text description of the video content
        
        Examples:
            # Simplest: use default (runninghub cloud)
            description = await military_video_gen.video_analysis("temp/01_segment.mp4")
            
            # Use local ComfyUI (future)
            description = await military_video_gen.video_analysis(
                "temp/01_segment.mp4",
                source="selfhost"
            )
            
            # Use specific workflow (bypass source-based resolution)
            description = await military_video_gen.video_analysis(
                "temp/01_segment.mp4",
                workflow="runninghub/custom_video_analysis.json"
            )
        """
        from military_video_gen.utils.workflow_util import resolve_workflow_path
        
        # 1. Validate video path
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise FileNotFoundError(
                f"Video file not found: {redact_path_for_log(video_path)}"
            )
        
        # 2. Resolve workflow path using convention
        if workflow is None:
            # Use standardized naming: {source}/analyse_video.json
            workflow = resolve_workflow_path("analyse_video", source)
            logger.info(f"Using {source} workflow: {workflow}")
        
        # 3. Resolve workflow (returns structured info)
        workflow_info = self._resolve_workflow(workflow=workflow)
        
        # 4. Build workflow parameters
        workflow_params = {
            "video": str(video_path)  # Pass video path to workflow
        }
        
        # Add any additional parameters
        workflow_params.update(params)
        
        logger.debug(f"Workflow parameters: {workflow_params}")
        
        # 5. Execute workflow using shared ComfyKit instance from core
        try:
            # Get shared ComfyKit instance (lazy initialization + config hot-reload)
            kit = await self.core._get_or_create_comfykit()
            
            # Determine what to pass to ComfyKit based on source
            if workflow_info["source"] == "runninghub" and "workflow_id" in workflow_info:
                # RunningHub: pass workflow_id
                workflow_input = workflow_info["workflow_id"]
                logger.info(f"Executing RunningHub workflow: {workflow_input}")
            else:
                # Selfhost: pass file path
                workflow_input = workflow_info.get("_internal_path", workflow_info["path"])
                logger.info(f"Executing selfhost workflow: {redact_path_for_log(workflow_input)}")
            
            result = await run_async_until_stopped(kit.execute(workflow_input, workflow_params))
            
            # 6. Extract description from result
            if result.status != "completed":
                error_msg = result.msg or "Unknown error"
                logger.error(f"Video analysis failed: {sanitize_error_message(error_msg)}")
                raise RuntimeError(
                    f"Video analysis failed: {sanitize_error_message(error_msg)}"
                )
            
            # Extract text description from result
            # Video understanding workflow returns text in result.texts array
            description = None
            
            # Format 1: Direct texts array (most common for video understanding)
            if result.texts and len(result.texts) > 0:
                description = result.texts[0]
                logger.debug(f"Found description in result.texts ({len(description)} chars)")
            
            # Format 2: Selfhost outputs (direct text in outputs)
            # Format: {'6': {'text': ['description text']}}
            elif result.outputs:
                for node_id, node_output in result.outputs.items():
                    if 'text' in node_output:
                        text_list = node_output['text']
                        if text_list and len(text_list) > 0:
                            description = text_list[0]
                            logger.debug(
                                f"Found description in outputs.text ({len(description)} chars)"
                            )
                            break
            
            # Format 3: RunningHub raw_data (text file URL)
            # Format: {'raw_data': [{'fileUrl': 'https://...txt', 'fileType': 'txt', ...}]}
            if not description and result.outputs and 'raw_data' in result.outputs:
                raw_data = result.outputs['raw_data']
                if raw_data and len(raw_data) > 0:
                    # Find text file entry
                    for item in raw_data:
                        if item.get('fileType') == 'txt' and 'fileUrl' in item:
                            # Download text content from URL
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(item['fileUrl']) as resp:
                                    if resp.status == 200:
                                        description = await resp.text()
                                        description = description.strip()
                                        logger.debug(
                                            "Downloaded description from provider URL "
                                            f"({len(description)} chars)"
                                        )
                                        break
            
            if not description:
                logger.error(
                    "No text found in video analysis result "
                    f"(status={result.status}, output_keys={sorted(result.outputs or {})}, "
                    f"text_count={len(result.texts or [])})"
                )
                raise Exception("No description generated from video analysis")
            
            logger.info(f"Video analyzed successfully ({len(description)} chars)")
            
            return description
        
        except Exception as e:
            logger.error(f"Video analysis error: {sanitize_error_message(e)}")
            raise
