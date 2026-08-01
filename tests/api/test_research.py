from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

import api.routers.research as research_router_module
from api.app import app
from api.routers.research import get_research_service
from api.tasks import task_manager
from military_video_gen.config import config_manager
from military_video_gen.database.base import Base
from military_video_gen.database.models import GenerationJob, Project
from military_video_gen.database.session import create_engine, get_db_session
from military_video_gen.research.models import ResearchSnapshot
from military_video_gen.research.monitor import ResearchMonitor


class FakeResearchService:
    async def run(self, request, *, progress):
        progress("searching", 1, 1)
        return ResearchSnapshot(
            topic=request.topic,
            input_hash="0" * 64,
            script_revision=request.script_revision,
            researched_at=datetime.now(UTC),
            research_status="reference_unavailable",
            verification_status="unverified",
            warnings=["test"],
        )


@pytest.fixture
async def research_client(tmp_path):
    task_manager._tasks.clear()
    task_manager._task_futures.clear()
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'research-api.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(Project(id="project-a", title="Project A"))
        await session.commit()

    async def override_session():
        async with factory() as session:
            yield session

    async def override_service():
        return FakeResearchService()

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_research_service] = override_service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.pop(get_db_session, None)
    app.dependency_overrides.pop(get_research_service, None)
    task_manager._tasks.clear()
    task_manager._task_futures.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_research_disabled_returns_503_without_creating_job(
    research_client,
    monkeypatch,
) -> None:
    client, factory = research_client
    monkeypatch.setattr(config_manager.config.research, "enabled", False)

    response = await client.post(
        "/api/content/research/async",
        json={
            "project_id": "project-a",
            "topic": "aircraft",
            "narrations": ["narration"],
            "script_revision": 1,
        },
    )

    assert response.status_code == 503
    async with factory() as session:
        assert await session.get(GenerationJob, response.json().get("job_id", "missing")) is None


@pytest.mark.asyncio
async def test_diagnostics_explains_disabled_research_without_probing_services(
    research_client,
    monkeypatch,
    tmp_path,
) -> None:
    client, _factory = research_client
    monkeypatch.setattr(config_manager.config.research, "enabled", False)
    monkeypatch.setattr(
        research_router_module,
        "research_monitor",
        ResearchMonitor(tmp_path / "research-monitor.jsonl"),
    )

    response = await client.get("/api/content/research/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "disabled"
    assert payload["enabled"] is False
    assert payload["services"]["searxng"]["status"] == "not_checked"
    assert payload["services"]["crawl4ai"]["status"] == "not_checked"
    assert payload["recent_events"] == []


@pytest.mark.asyncio
async def test_create_research_job_persists_request_without_token(
    research_client,
    monkeypatch,
) -> None:
    client, factory = research_client
    monkeypatch.setattr(config_manager.config.research, "enabled", True)

    async def hold_task(**_kwargs):
        return None

    monkeypatch.setattr(task_manager, "execute_task", hold_task)
    response = await client.post(
        "/api/content/research/async",
        json={
            "project_id": "project-a",
            "topic": "aircraft",
            "narrations": ["narration"],
            "script_revision": 1,
        },
    )

    assert response.status_code == 202
    async with factory() as session:
        job = await session.get(GenerationJob, response.json()["job_id"])
        assert job.job_type == "research"
        assert job.params_json["topic"] == "aircraft"
        assert "token" not in repr(job.params_json).lower()


@pytest.mark.asyncio
async def test_unavailable_reference_still_writes_completed_job_event(
    research_client,
    monkeypatch,
    tmp_path,
) -> None:
    client, _factory = research_client
    monitor = ResearchMonitor(tmp_path / "research-monitor.jsonl")
    monkeypatch.setattr(config_manager.config.research, "enabled", True)
    monkeypatch.setattr(research_router_module, "research_monitor", monitor)

    async def execute_immediately(*, task_id, coro_func):
        assert task_id
        await coro_func()

    monkeypatch.setattr(task_manager, "execute_task", execute_immediately)
    response = await client.post(
        "/api/content/research/async",
        json={
            "project_id": "project-a",
            "topic": "aircraft",
            "narrations": ["narration"],
            "script_revision": 1,
        },
    )

    assert response.status_code == 202
    events = list(reversed(monitor.read_recent()))
    assert [event["event"] for event in events] == [
        "job_created",
        "phase_progress",
        "job_completed",
    ]
    assert all(event["job_id"] == response.json()["job_id"] for event in events)
    assert events[-1]["status"] == "completed"
    assert events[-1]["metrics"]["research_status"] == "reference_unavailable"
    assert not any(event["event"] == "job_failed" for event in events)
    assert "aircraft" not in monitor.path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_retry_records_parent_in_column_and_params(
    research_client,
    monkeypatch,
) -> None:
    client, factory = research_client
    monkeypatch.setattr(config_manager.config.research, "enabled", True)
    async with factory() as session:
        session.add(
            GenerationJob(
                id="old-research",
                project_id="project-a",
                job_type="research",
                status="failed",
                params_json={
                    "project_id": "project-a",
                    "topic": "aircraft",
                    "narrations": ["narration"],
                    "asset_type": "video",
                    "mode": "verified",
                    "script_revision": 1,
                },
            )
        )
        await session.commit()

    async def hold_task(**_kwargs):
        return None

    monkeypatch.setattr(task_manager, "execute_task", hold_task)
    response = await client.post(
        "/api/content/research/old-research/retry",
        json={"parent_job_id": "old-research", "force_refresh": True},
    )

    assert response.status_code == 202
    async with factory() as session:
        job = await session.get(GenerationJob, response.json()["job_id"])
        assert job.parent_job_id == "old-research"
        assert job.params_json["parent_job_id"] == "old-research"

    mismatch = await client.post(
        "/api/content/research/old-research/retry",
        json={"parent_job_id": "different"},
    )
    assert mismatch.status_code == 422
