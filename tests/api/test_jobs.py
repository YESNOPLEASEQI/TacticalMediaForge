from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.app import app
from api.routers.jobs import _read
from api.tasks import Task, TaskProgress, TaskStatus, TaskType, task_manager
from military_video_gen.database.base import Base
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.session import create_engine, get_db_session


@pytest.mark.asyncio
async def test_active_and_project_job_queries_are_database_backed(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add_all(
            [
                Project(id="project-a", title="A"),
                Project(id="project-b", title="B"),
                GenerationJob(
                    id="job-a",
                    project_id="project-a",
                    job_type="script_generation",
                    status="running",
                ),
                GenerationJob(
                    id="job-b",
                    project_id="project-b",
                    job_type="video_generation",
                    status="completed",
                ),
            ]
        )
        await session.commit()

    async def override_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            active = await client.get("/api/jobs", params={"active": "true"})
            project_jobs = await client.get("/api/projects/project-b/jobs")
            one_job = await client.get("/api/jobs/job-a")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        await engine.dispose()

    assert active.status_code == 200
    assert [item["id"] for item in active.json()] == ["job-a"]
    assert [item["id"] for item in project_jobs.json()] == ["job-b"]
    assert one_job.json()["project_id"] == "project-a"


def test_terminal_database_result_is_not_masked_by_stale_completed_task(monkeypatch):
    job = GenerationJob(
        id="completed-job",
        project_id="project-a",
        job_type="video_generation",
        provider="local",
        status="completed",
        progress=100,
        params_json={},
        result_json={"file_size": 114571},
        created_at=datetime.now(timezone.utc),
    )
    stale_task = Task(
        task_id=job.id,
        task_type=TaskType.VIDEO_GENERATION,
        status=TaskStatus.COMPLETED,
        result={"file_size": 113732},
    )
    monkeypatch.setattr(task_manager, "get_task", lambda _task_id: stale_task)

    assert _read(job).result_json == {"file_size": 114571}


def test_active_runtime_task_still_overlays_database_progress(monkeypatch):
    job = GenerationJob(
        id="running-job",
        project_id="project-a",
        job_type="video_generation",
        provider="local",
        status="running",
        progress=10,
        params_json={},
        result_json={},
        created_at=datetime.now(timezone.utc),
    )
    active_task = Task(
        task_id=job.id,
        task_type=TaskType.VIDEO_GENERATION,
        status=TaskStatus.RUNNING,
        result={"partial": True},
        progress=TaskProgress(current=3500, total=10000, percentage=35, message="生成素材", stage="media", current_scene=2, total_scenes=5),
    )
    monkeypatch.setattr(task_manager, "get_task", lambda _task_id: active_task)

    result = _read(job)
    assert result.status == "running"
    assert result.result_json == {"partial": True}
    assert result.progress_current_scene == 2
    assert result.progress_total_scenes == 5
    assert result.progress_stage == "media"
