"""
API Routers
"""

from api.routers.content import router as content_router
from api.routers.files import router as files_router
from api.routers.frame import router as frame_router
from api.routers.health import router as health_router
from api.routers.history import router as history_router
from api.routers.image import router as image_router
from api.routers.jobs import router as jobs_router
from api.routers.llm import router as llm_router
from api.routers.projects import router as projects_router
from api.routers.research import router as research_router
from api.routers.resources import router as resources_router
from api.routers.tasks import router as tasks_router
from api.routers.tts import router as tts_router
from api.routers.video import router as video_router

__all__ = [
    "health_router",
    "llm_router",
    "tts_router",
    "image_router",
    "content_router",
    "video_router",
    "tasks_router",
    "files_router",
    "resources_router",
    "frame_router",
    "history_router",
    "projects_router",
    "jobs_router",
    "research_router",
]

