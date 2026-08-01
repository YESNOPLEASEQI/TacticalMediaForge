import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.tasks.models import Task, TaskStatus, TaskType
from military_video_gen.database.base import Base
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.runtime_jobs import (
    INTERRUPTED_JOB_ERROR,
    create_runtime_job,
    reconcile_interrupted_jobs,
    sync_runtime_job,
)
from military_video_gen.database.session import create_engine


@pytest.mark.asyncio
async def test_runtime_job_lifecycle_updates_database_and_project(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'runtime-jobs.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="A"))
        await session.commit()

    task = Task(
        task_id="job-a",
        task_type=TaskType.SCRIPT_GENERATION,
        request_params={"project_id": "project-a", "text": "source"},
    )
    assert await create_runtime_job(
        project_id="project-a",
        task=task,
        job_type="script_generation",
        factory=factory,
    )
    task.status = TaskStatus.COMPLETED
    task.result = {"narrations": ["segment"]}
    await sync_runtime_job(task, factory=factory)

    async with factory() as session:
        job = await session.get(GenerationJob, "job-a")
        project = await session.get(Project, "project-a")
        assert job.status == "completed"
        assert job.result_json == {"narrations": ["segment"]}
        assert project.current_stage == "storyboard"
    await engine.dispose()


@pytest.mark.asyncio
async def test_completed_research_atomically_becomes_active_without_advancing_stage(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'research-runtime.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(
            Project(
                id="project-a",
                title="A",
                current_stage="storyboard",
                settings_json={"active_research_job_id": "old-job"},
            )
        )
        await session.commit()

    task = Task(
        task_id="research-job",
        task_type=TaskType.RESEARCH,
        request_params={"project_id": "project-a"},
    )
    assert await create_runtime_job(
        project_id="project-a",
        task=task,
        job_type="research",
        factory=factory,
    )
    task.status = TaskStatus.COMPLETED
    task.result = {"verification_status": "verified"}
    await sync_runtime_job(task, factory=factory)

    async with factory() as session:
        project = await session.get(Project, "project-a")
        assert project.settings_json["active_research_job_id"] == "research-job"
        assert project.current_stage == "storyboard"
    await engine.dispose()


@pytest.mark.asyncio
async def test_older_job_type_cannot_regress_project_stage(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'monotonic-stage.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="A", current_stage="output"))
        await session.commit()

    task = Task(task_id="late-script", task_type=TaskType.SCRIPT_GENERATION)
    assert await create_runtime_job(
        project_id="project-a",
        task=task,
        job_type="script_generation",
        factory=factory,
    )
    task.status = TaskStatus.COMPLETED
    task.result = {"narrations": ["late"]}
    await sync_runtime_job(task, factory=factory)

    async with factory() as session:
        project = await session.get(Project, "project-a")
        assert project.current_stage == "output"
    await engine.dispose()


@pytest.mark.asyncio
async def test_reconcile_interrupted_jobs_only_fails_active_jobs(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'reconcile.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="A"))
        session.add_all(
            GenerationJob(
                id=f"job-{status}",
                project_id="project-a",
                job_type="video_generation",
                provider="local",
                external_job_id=f"job-{status}",
                status=status,
            )
            for status in ("pending", "queued", "running", "completed", "failed", "cancelled")
        )
        await session.commit()

    assert await reconcile_interrupted_jobs(factory=factory) == 3

    async with factory() as session:
        for status in ("pending", "queued", "running"):
            job = await session.get(GenerationJob, f"job-{status}")
            assert job.status == "failed"
            assert job.error_message == INTERRUPTED_JOB_ERROR
            assert job.completed_at is not None
        for status in ("completed", "failed", "cancelled"):
            job = await session.get(GenerationJob, f"job-{status}")
            assert job.status == status
            assert job.error_message is None
            assert job.completed_at is None
    await engine.dispose()
