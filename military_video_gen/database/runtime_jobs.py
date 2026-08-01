"""Persist the lifecycle of in-memory background tasks as GenerationJob rows."""

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.tasks.models import Task
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.session import AsyncSessionFactory

STAGE_AFTER_JOB = {
    "script_generation": "storyboard",
    "storyboard_generation": "video",
    "video_generation": "output",
}
STAGE_ORDER = {
    "script": 0,
    "storyboard": 1,
    "video": 2,
    "output": 3,
}

INTERRUPTED_JOB_ERROR = "Task interrupted because the application restarted"


async def reconcile_interrupted_jobs(
    *,
    factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
) -> int:
    """Mark persisted jobs whose in-memory task was lost during a restart."""
    completed_at = datetime.now(timezone.utc)
    async with factory() as session:
        result = await session.execute(
            update(GenerationJob)
            .where(GenerationJob.status.in_(("pending", "queued", "running")))
            .values(
                status="failed",
                error_message=INTERRUPTED_JOB_ERROR,
                completed_at=completed_at,
            )
        )
        await session.commit()
        return result.rowcount


async def create_runtime_job(
    *,
    project_id: str,
    task: Task,
    job_type: str,
    factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    session: AsyncSession | None = None,
) -> bool:
    async def create(active_session: AsyncSession) -> bool:
        project = await active_session.get(Project, project_id)
        if project is None or project.deleted_at is not None:
            return False
        job = GenerationJob(
            id=task.task_id,
            project_id=project_id,
            job_type=job_type,
            provider="local",
            status=task.status.value,
            external_job_id=task.task_id,
            params_json=task.request_params or {},
            parent_job_id=(task.request_params or {}).get("parent_job_id"),
        )
        active_session.add(job)
        project.status = "active"
        await active_session.commit()
        return True

    if session is not None:
        return await create(session)
    async with factory() as owned_session:
        return await create(owned_session)


async def sync_runtime_job(
    task: Task,
    *,
    factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
) -> None:
    async with factory() as session:
        job = await session.get(GenerationJob, task.task_id)
        if job is None:
            return
        job.status = task.status.value
        job.progress = task.progress.percentage if task.progress else (100.0 if task.status.value == "completed" else job.progress)
        job.result_json = task.result if isinstance(task.result, dict) else {}
        job.error_message = task.error
        job.started_at = task.started_at
        job.completed_at = task.completed_at
        if task.status.value == "completed":
            project = await session.get(Project, job.project_id)
            if project is not None:
                next_stage = STAGE_AFTER_JOB.get(job.job_type)
                if next_stage is not None and STAGE_ORDER.get(next_stage, -1) >= STAGE_ORDER.get(
                    project.current_stage or "script",
                    -1,
                ):
                    project.current_stage = next_stage
                project.updated_at = datetime.now(timezone.utc)
                if job.job_type == "video_generation":
                    project.status = "completed"
                elif job.job_type == "research":
                    project.settings_json = {
                        **(project.settings_json or {}),
                        "active_research_job_id": job.id,
                    }
        await session.commit()
