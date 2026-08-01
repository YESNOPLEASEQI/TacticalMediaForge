import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.tasks.manager import SHUTDOWN_CANCELLATION_REASON, TASK_CANCELLATION_REASON, TaskManager
from api.tasks.models import TaskStatus, TaskType
from military_video_gen.database.base import Base
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.runtime_jobs import create_runtime_job, sync_runtime_job
from military_video_gen.database.session import create_engine


async def _manager_with_job(tmp_path, monkeypatch, job_id):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / (job_id + '.db')}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="A"))
        await session.commit()

    manager = TaskManager()
    task = manager.create_task(TaskType.VIDEO_GENERATION, {"project_id": "project-a"})
    task.task_id = job_id
    manager._tasks = {job_id: task}
    await create_runtime_job(
        project_id="project-a",
        task=task,
        job_type="video_generation",
        factory=factory,
    )

    async def persist(runtime_task):
        await sync_runtime_job(runtime_task, factory=factory)

    monkeypatch.setattr(manager, "_sync_runtime_job", persist)
    return manager, task, factory, engine


@pytest.mark.asyncio
async def test_stop_cancels_and_persists_active_task(tmp_path, monkeypatch):
    manager, task, factory, engine = await _manager_with_job(tmp_path, monkeypatch, "shutdown-job")
    started = asyncio.Event()

    async def work():
        started.set()
        await asyncio.Event().wait()

    await manager.start()
    await manager.execute_task(task.task_id, work)
    await started.wait()
    await manager.stop()

    assert manager._tasks == {}
    async with factory() as session:
        job = await session.get(GenerationJob, task.task_id)
        assert job.status == "cancelled"
        assert job.error_message == SHUTDOWN_CANCELLATION_REASON
        assert job.completed_at is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_cancelled_error_is_synced_before_being_rethrown(tmp_path, monkeypatch):
    manager, task, factory, engine = await _manager_with_job(tmp_path, monkeypatch, "cancelled-job")
    started = asyncio.Event()

    async def work():
        started.set()
        await asyncio.Event().wait()

    await manager.execute_task(task.task_id, work)
    await started.wait()
    future = manager._task_futures[task.task_id]
    future.cancel()
    with pytest.raises(asyncio.CancelledError):
        await future

    async with factory() as session:
        job = await session.get(GenerationJob, task.task_id)
        assert job.status == TaskStatus.CANCELLED.value
        assert job.error_message == TASK_CANCELLATION_REASON
        assert job.completed_at is not None
    await manager.stop()
    await engine.dispose()
