"""Asynchronous web-reference storyboard enhancement endpoints."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_military_video_gen
from api.schemas.content import (
    ContentJobResponse,
    ResearchCreateRequest,
    ResearchRetryRequest,
)
from api.tasks import TaskType, task_manager
from military_video_gen.config import config_manager
from military_video_gen.database.models import GenerationJob
from military_video_gen.database.runtime_jobs import create_runtime_job
from military_video_gen.database.session import get_db_session
from military_video_gen.research.models import ResearchRequest
from military_video_gen.research.monitor import (
    collect_research_diagnostics,
    research_monitor,
)
from military_video_gen.research.service import ResearchService, build_research_service
from military_video_gen.utils.safety import sanitize_error_message

router = APIRouter(prefix="/content/research", tags=["Research"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_research_service() -> ResearchService:
    research_config = config_manager.config.research
    if not research_config.enabled:
        raise HTTPException(status_code=503, detail="research capability is disabled")
    core = await get_military_video_gen()
    return build_research_service(research_config, core.llm)


ResearchServiceDep = Annotated[ResearchService, Depends(get_research_service)]


def _ensure_enabled() -> None:
    if not config_manager.config.research.enabled:
        raise HTTPException(status_code=503, detail="research capability is disabled")


@router.get("/diagnostics")
async def get_diagnostics():
    return await collect_research_diagnostics(
        config_manager.config.research,
        monitor=research_monitor,
    )


async def _create_job(
    request: ResearchRequest,
    service: ResearchService,
    session: AsyncSession,
) -> ContentJobResponse:
    task, created_new = task_manager.create_or_get_task(
        task_type=TaskType.RESEARCH,
        request_params=request.model_dump(mode="json"),
    )
    if not created_new:
        return ContentJobResponse(job_id=task.task_id)
    created = await create_runtime_job(
        project_id=request.project_id,
        task=task,
        job_type="research",
        session=session,
    )
    if not created:
        task_manager.discard_pending_task(task.task_id)
        raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")
    research_monitor.record(
        event="job_created",
        status="pending",
        job_id=task.task_id,
        project_id=request.project_id,
        metrics={
            "scene_count": len(request.narrations),
            "script_revision": request.script_revision,
        },
    )

    async def execute_research():
        def update_progress(phase, current: int, total: int) -> None:
            stage = phase.value if hasattr(phase, "value") else str(phase)
            task_manager.update_progress(
                task.task_id,
                current,
                total,
                message=stage.replace("_", " "),
                stage=stage,
            )
            research_monitor.record(
                event="phase_progress",
                status="running",
                job_id=task.task_id,
                project_id=request.project_id,
                phase=stage,
                metrics={"current": current, "total": total},
            )

        try:
            snapshot = await service.run(request, progress=update_progress)
        except asyncio.CancelledError:
            research_monitor.record(
                event="job_cancelled",
                status="cancelled",
                job_id=task.task_id,
                project_id=request.project_id,
            )
            raise
        except Exception as error:
            research_monitor.record(
                event="job_failed",
                status="failed",
                job_id=task.task_id,
                project_id=request.project_id,
                message=(
                    f"{type(error).__name__}: {sanitize_error_message(error)}"
                ),
            )
            raise
        research_monitor.record(
            event="job_completed",
            status="completed",
            job_id=task.task_id,
            project_id=request.project_id,
            metrics={
                "research_status": snapshot.research_status.value,
                "source_count": len(snapshot.sources),
                "claim_count": len(snapshot.claims),
                "scene_count": len(snapshot.storyboard_plan),
                "warning_count": len(snapshot.warnings),
            },
        )
        return snapshot.model_dump(mode="json")

    await task_manager.execute_task(
        task_id=task.task_id,
        coro_func=execute_research,
    )
    return ContentJobResponse(job_id=task.task_id)


@router.post(
    "/async",
    response_model=ContentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_research(
    payload: ResearchCreateRequest,
    service: ResearchServiceDep,
    session: DBSession,
):
    _ensure_enabled()
    return await _create_job(
        ResearchRequest.model_validate(payload.model_dump()),
        service,
        session,
    )


@router.post(
    "/{job_id}/retry",
    response_model=ContentJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_research(
    job_id: str,
    payload: ResearchRetryRequest,
    service: ResearchServiceDep,
    session: DBSession,
):
    _ensure_enabled()
    if payload.parent_job_id != job_id:
        raise HTTPException(
            status_code=422,
            detail="request parent_job_id must match the path job_id",
        )
    parent = await session.get(GenerationJob, job_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if parent.job_type != "research":
        raise HTTPException(status_code=409, detail="only research jobs can be retried")
    if parent.status not in {"completed", "success", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="an active research job cannot be retried")
    active_child = await session.scalar(
        select(GenerationJob).where(
            GenerationJob.parent_job_id == job_id,
            GenerationJob.status.in_(("pending", "queued", "running")),
        )
    )
    if active_child is not None:
        return ContentJobResponse(job_id=active_child.id)
    if payload.request and payload.request.project_id != parent.project_id:
        raise HTTPException(status_code=409, detail="retry project must match the parent job")
    replacement = payload.request.model_dump() if payload.request else {}
    params = {
        **(parent.params_json or {}),
        **replacement,
        "parent_job_id": job_id,
        "force_refresh": payload.force_refresh,
    }
    return await _create_job(
        ResearchRequest.model_validate(params),
        service,
        session,
    )
