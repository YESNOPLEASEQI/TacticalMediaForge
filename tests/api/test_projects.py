import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.routers.projects import router
from military_video_gen.database.base import Base
from military_video_gen.database.models import Project
from military_video_gen.database.session import create_engine, get_db_session


@pytest.fixture
async def project_client(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'projects.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_crud_and_soft_delete(project_client):
    client, factory = project_client

    created = await client.post(
        "/api/projects",
        json={"title": "Radar Documentary", "source_text": "source", "settings_json": {"fps": 30}},
    )
    assert created.status_code == 201
    project = created.json()
    assert project["title"] == "Radar Documentary"
    assert project["status"] == "draft"

    listed = await client.get("/api/projects", params={"status": "draft"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [project["id"]]

    patched = await client.patch(
        f"/api/projects/{project['id']}",
        json={
            "title": "Updated Radar",
            "status": "active",
            "settings_json": {"workspace_draft": {"stage": "script"}},
        },
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Updated Radar"
    assert patched.json()["status"] == "active"
    assert patched.json()["settings_json"] == {
        "fps": 30,
        "workspace_draft": {"stage": "script"},
    }

    deleted = await client.delete(f"/api/projects/{project['id']}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/projects/{project['id']}")
    assert missing.status_code == 404
    assert (await client.get("/api/projects")).json() == []

    async with factory() as session:
        stored = await session.scalar(select(Project).where(Project.id == project["id"]))
        assert stored is not None
        assert stored.deleted_at is not None


@pytest.mark.asyncio
async def test_project_patch_rejects_empty_title(project_client):
    client, _factory = project_client
    created = await client.post("/api/projects", json={"title": "Valid"})

    response = await client.patch(
        f"/api/projects/{created.json()['id']}",
        json={"title": "   "},
    )

    assert response.status_code == 422
