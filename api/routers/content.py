"""
Content generation endpoints

Endpoints for generating narrations, image prompts, and titles.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from api.dependencies import MilitaryVideoGenDep
from api.errors import internal_server_error
from api.schemas.content import (
    ContentJobResponse,
    ImagePromptGenerateRequest,
    ImagePromptGenerateResponse,
    NarrationGenerateRequest,
    NarrationGenerateResponse,
    ProjectImagePromptGenerateRequest,
    ProjectNarrationGenerateRequest,
    TitleGenerateRequest,
    TitleGenerateResponse,
)
from api.tasks import TaskType, task_manager
from military_video_gen.config import config_manager
from military_video_gen.database.runtime_jobs import create_runtime_job
from military_video_gen.research.script_service import generate_researched_narrations
from military_video_gen.utils.content_generators import (
    generate_image_prompts,
    generate_narrations_from_topic,
    generate_title,
    generate_video_prompts,
)

router = APIRouter(prefix="/content", tags=["Content Generation"])


@router.post("/narration/async", response_model=ContentJobResponse)
async def generate_narration_async(
    request: ProjectNarrationGenerateRequest,
    military_video_gen: MilitaryVideoGenDep,
):
    task, created = task_manager.create_or_get_task(
        task_type=TaskType.SCRIPT_GENERATION,
        request_params=request.model_dump(),
    )
    if not created:
        return ContentJobResponse(job_id=task.task_id)
    if not await create_runtime_job(
        project_id=request.project_id,
        task=task,
        job_type="script_generation",
    ):
        task_manager.discard_pending_task(task.task_id)
        raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

    async def execute():
        if request.mode == "quick":
            narrations = await generate_narrations_from_topic(
                llm_service=military_video_gen.llm,
                topic=request.text,
                n_scenes=request.n_scenes,
                min_words=request.min_words,
                max_words=request.max_words,
            )
            return {
                "narrations": narrations,
                "research_status": "quick",
                "queries": [],
                "sources": [],
            }
        researched = await generate_researched_narrations(
            llm_service=military_video_gen.llm,
            research_config=config_manager.config.research,
            project_id=request.project_id,
            topic=request.text,
            n_scenes=request.n_scenes,
            min_words=request.min_words,
            max_words=request.max_words,
            require_references=False,
        )
        return {
            "narrations": researched.narrations,
            "research_status": researched.research_status,
            "queries": researched.queries,
            "sources": researched.sources,
            "warnings": getattr(researched, "warnings", []),
        }

    await task_manager.execute_task(task.task_id, execute)
    return ContentJobResponse(job_id=task.task_id)


@router.post("/image-prompt/async", response_model=ContentJobResponse)
async def generate_image_prompt_async(
    request: ProjectImagePromptGenerateRequest,
    military_video_gen: MilitaryVideoGenDep,
):
    task, created = task_manager.create_or_get_task(
        task_type=TaskType.STORYBOARD_GENERATION,
        request_params=request.model_dump(),
    )
    if not created:
        return ContentJobResponse(job_id=task.task_id)
    if not await create_runtime_job(
        project_id=request.project_id,
        task=task,
        job_type="storyboard_generation",
    ):
        task_manager.discard_pending_task(task.task_id)
        raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

    async def execute():
        prompt_generator = (
            generate_video_prompts
            if request.asset_type == "video"
            else generate_image_prompts
        )
        prompts = await prompt_generator(
            llm_service=military_video_gen.llm,
            narrations=request.narrations,
            min_words=request.min_words,
            max_words=request.max_words,
        )
        return {"image_prompts": prompts}

    await task_manager.execute_task(task.task_id, execute)
    return ContentJobResponse(job_id=task.task_id)


@router.post("/narration", response_model=NarrationGenerateResponse)
async def generate_narration(
    request: NarrationGenerateRequest,
    military_video_gen: MilitaryVideoGenDep
):
    """
    Generate narrations from text
    
    Uses LLM to break down text into multiple narration segments.
    
    - **text**: Source text
    - **n_scenes**: Number of narrations to generate
    - **min_words**: Minimum words per narration
    - **max_words**: Maximum words per narration
    
    Returns list of narration strings.
    """
    try:
        logger.info(f"Generating {request.n_scenes} narrations from text")
        
        if request.mode == "quick":
            narrations = await generate_narrations_from_topic(
                llm_service=military_video_gen.llm,
                topic=request.text,
                n_scenes=request.n_scenes,
                min_words=request.min_words,
                max_words=request.max_words,
            )
        else:
            researched = await generate_researched_narrations(
                llm_service=military_video_gen.llm,
                research_config=config_manager.config.research,
                project_id="synchronous-script-request",
                topic=request.text,
                n_scenes=request.n_scenes,
                min_words=request.min_words,
                max_words=request.max_words,
                require_references=False,
            )
            narrations = researched.narrations

        return NarrationGenerateResponse(narrations=narrations)
        
    except Exception as e:
        raise internal_server_error("Narration generation error", e)


@router.post("/image-prompt", response_model=ImagePromptGenerateResponse)
async def generate_image_prompt(
    request: ImagePromptGenerateRequest,
    military_video_gen: MilitaryVideoGenDep
):
    """
    Generate image prompts from narrations
    
    Uses LLM to create detailed image generation prompts.
    
    - **narrations**: List of narration texts
    - **min_words**: Minimum words per prompt
    - **max_words**: Maximum words per prompt
    
    Returns list of image prompts.
    """
    try:
        logger.info(f"Generating image prompts for {len(request.narrations)} narrations")
        
        # Call image prompt generator utility function
        image_prompts = await generate_image_prompts(
            llm_service=military_video_gen.llm,
            narrations=request.narrations,
            min_words=request.min_words,
            max_words=request.max_words
        )
        
        return ImagePromptGenerateResponse(
            image_prompts=image_prompts
        )
        
    except Exception as e:
        raise internal_server_error("Image prompt generation error", e)


@router.post("/title", response_model=TitleGenerateResponse)
async def generate_title_endpoint(
    request: TitleGenerateRequest,
    military_video_gen: MilitaryVideoGenDep
):
    """
    Generate video title from text
    
    Uses LLM to create an engaging title.
    
    - **text**: Source text
    - **style**: Optional title style hint
    
    Returns generated title.
    """
    try:
        logger.info("Generating title from text")
        
        # Call title generator utility function
        title = await generate_title(
            llm_service=military_video_gen.llm,
            content=request.text,
            strategy="llm"
        )
        
        return TitleGenerateResponse(
            title=title
        )
        
    except Exception as e:
        raise internal_server_error("Title generation error", e)

