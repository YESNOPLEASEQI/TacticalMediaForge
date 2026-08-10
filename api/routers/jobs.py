"""Database-backed generation job queries with live task progress overlay."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.public_paths import sanitize_public_payload
from api.schemas.jobs import GenerationJobRead
from api.tasks import task_manager
from military_video_gen.database.models import GenerationJob
from military_video_gen.database.session import get_db_session
from military_video_gen.utils.safety import sanitize_error_message

router = APIRouter(tags=["Generation Jobs"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
ACTIVE_STATUSES = {"pending", "queued", "running"}


def _read(job: GenerationJob) -> GenerationJobRead:
    payload = GenerationJobRead.model_validate(job)
    if payload.status == "success":
        payload = payload.model_copy(update={"status": "completed"})
    elif payload.status == "queued":
        payload = payload.model_copy(update={"status": "pending"})
    task = task_manager.get_task(job.id)
    # Runtime state is authoritative while either side is still active. Once
    # both records are terminal, the database is the canonical durable result;
    # retaining an old completed task in memory must not mask a repaired or
    # reconciled result_json value.
    if task is not None and (
        payload.status in ACTIVE_STATUSES or task.status.value in ACTIVE_STATUSES
    ):
        status = task.status.value
        progress = task.progress.percentage if task.progress else payload.progress
        payload = payload.model_copy(
            update={
                "status": status,
                "progress": progress,
                "result_json": task.result or payload.result_json,
                "error_message": task.error or payload.error_message,
                "started_at": task.started_at or payload.started_at,
                "completed_at": task.completed_at or payload.completed_at,
                "progress_stage": task.progress.stage if task.progress else None,
                "progress_message": task.progress.message if task.progress else None,
                "progress_current_scene": task.progress.current_scene if task.progress else None,
                "progress_total_scenes": task.progress.total_scenes if task.progress else None,
            }
        )
    return payload.model_copy(
        update={
            "params_json": sanitize_public_payload(payload.params_json),
            "result_json": sanitize_public_payload(payload.result_json),
            "error_message": (
                sanitize_error_message(payload.error_message)
                if payload.error_message
                else None
            ),
        }
    )


@router.get("/jobs", response_model=list[GenerationJobRead])
async def list_jobs(
    session: DBSession,
    active: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
):
    statement = select(GenerationJob)
    if active:
        statement = statement.where(GenerationJob.status.in_(ACTIVE_STATUSES))
    jobs = (await session.scalars(statement.order_by(GenerationJob.created_at.desc()).limit(limit))).all()
    return [_read(job) for job in jobs]


@router.get("/projects/{project_id}/jobs", response_model=list[GenerationJobRead])
async def list_project_jobs(project_id: str, session: DBSession):
    jobs = (
        await session.scalars(
            select(GenerationJob)
            .where(GenerationJob.project_id == project_id)
            .order_by(GenerationJob.created_at.desc())
        )
    ).all()
    return [_read(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=GenerationJobRead)
async def get_job(job_id: str, session: DBSession):
    job = await session.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return _read(job)
