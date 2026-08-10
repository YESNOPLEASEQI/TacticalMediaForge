"""
MilitaryVideoGen FastAPI Application

Main FastAPI app with all routers and middleware.

Run this script to start the FastAPI server:
    uv run python api/app.py
    
Or with custom settings:
    uv run python api/app.py --host 127.0.0.1 --port 8080 --reload
"""

# ruff: noqa: E402 -- path bootstrapping must precede local package imports.

import sys
from pathlib import Path

# Add project root to sys.path for module imports
# This ensures imports work correctly in both development and packaged environments
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.config import api_config
from api.dependencies import shutdown_military_video_gen

# Import routers
from api.routers import (
    content_router,
    files_router,
    frame_router,
    health_router,
    history_router,
    image_router,
    jobs_router,
    llm_router,
    projects_router,
    reference_assets_router,
    research_router,
    resources_router,
    tasks_router,
    tts_router,
    video_router,
)
from api.tasks import task_manager
from military_video_gen.database.legacy_prompt_cleanup import clean_legacy_prompt_records
from military_video_gen.database.runtime_jobs import reconcile_interrupted_jobs
from military_video_gen.database.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("🚀 Starting MilitaryVideoGen API...")
    cleanup = await clean_legacy_prompt_records()
    if cleanup.projects or cleanup.removed_strings:
        logger.warning(
            "Removed retired storyboard prompts: projects={} jobs={} scenes={} "
            "assets={} script_versions={} strings={}",
            cleanup.projects,
            cleanup.jobs,
            cleanup.scenes,
            cleanup.assets,
            cleanup.script_versions,
            cleanup.removed_strings,
        )
    await reconcile_interrupted_jobs()
    await task_manager.start()
    logger.info("✅ MilitaryVideoGen API started successfully\n")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down MilitaryVideoGen API...")
    await task_manager.stop()
    await shutdown_military_video_gen()
    await dispose_engine()
    logger.info("✅ MilitaryVideoGen API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="MilitaryVideoGen API",
    description="""
    ## MilitaryVideoGen - AI Video Generation Platform API
    
    ### Features
    - 🤖 **LLM**: Large language model integration
    - 🔊 **TTS**: Text-to-speech synthesis
    - 🎨 **Image**: AI image generation
    - 📝 **Content**: Automated content generation
    - 🎬 **Video**: End-to-end video generation
    
    ### Video Generation Modes
    - **Sync**: `/api/video/generate/sync` - For small videos (< 30s)
    - **Async**: `/api/video/generate/async` - For large videos with task tracking
    
    ### Getting Started
    1. Check health: `GET /health`
    2. Generate narrations: `POST /api/content/narration`
    3. Generate video: `POST /api/video/generate/sync` or `/async`
    4. Track task progress: `GET /api/tasks/{task_id}`
    """,
    version="0.1.0",
    docs_url=api_config.docs_url,
    redoc_url=api_config.redoc_url,
    openapi_url=api_config.openapi_url,
    lifespan=lifespan,
)

# Add CORS middleware
if api_config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled for origins: {api_config.cors_origins}")

# Include routers
# Health check (no prefix)
app.include_router(health_router)

# API routers (with /api prefix)
app.include_router(llm_router, prefix=api_config.api_prefix)
app.include_router(tts_router, prefix=api_config.api_prefix)
app.include_router(image_router, prefix=api_config.api_prefix)
app.include_router(content_router, prefix=api_config.api_prefix)
app.include_router(video_router, prefix=api_config.api_prefix)
app.include_router(tasks_router, prefix=api_config.api_prefix)
app.include_router(files_router, prefix=api_config.api_prefix)
app.include_router(resources_router, prefix=api_config.api_prefix)
app.include_router(frame_router, prefix=api_config.api_prefix)
app.include_router(history_router, prefix=api_config.api_prefix)
app.include_router(projects_router, prefix=api_config.api_prefix)
app.include_router(reference_assets_router, prefix=api_config.api_prefix)
app.include_router(jobs_router, prefix=api_config.api_prefix)
app.include_router(research_router, prefix=api_config.api_prefix)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "MilitaryVideoGen API",
        "version": "0.1.0",
        "docs": api_config.docs_url,
        "health": "/health",
        "api": {
            "llm": f"{api_config.api_prefix}/llm",
            "tts": f"{api_config.api_prefix}/tts",
            "image": f"{api_config.api_prefix}/image",
            "content": f"{api_config.api_prefix}/content",
            "video": f"{api_config.api_prefix}/video",
            "tasks": f"{api_config.api_prefix}/tasks",
            "files": f"{api_config.api_prefix}/files",
            "resources": f"{api_config.api_prefix}/resources",
            "frame": f"{api_config.api_prefix}/frame",
            "history": f"{api_config.api_prefix}/sessions",
            "projects": f"{api_config.api_prefix}/projects",
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start MilitaryVideoGen API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    # Print startup banner
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    MilitaryVideoGen API Server                      ║
╚══════════════════════════════════════════════════════════════╝

Starting server at http://{args.host}:{args.port}
API Docs: http://{args.host}:{args.port}/docs
ReDoc: http://{args.host}:{args.port}/redoc

Press Ctrl+C to stop the server
""")
    
    # Start server
    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )

