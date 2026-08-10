import io

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker

from api.routers.projects import router as projects_router
from api.routers.reference_assets import router as reference_assets_router
from military_video_gen.database.base import Base
from military_video_gen.database.session import create_engine, get_db_session


def image_bytes(image_format: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (24, 64, 96)).save(buffer, format=image_format)
    return buffer.getvalue()


@pytest.fixture
async def reference_client(tmp_path, monkeypatch):
    monkeypatch.setenv("MILITARY_VIDEO_GEN_ROOT", str(tmp_path / "data"))
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'references.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(projects_router, prefix="/api")
    app.include_router(reference_assets_router, prefix="/api")
    app.dependency_overrides[get_db_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    await engine.dispose()


async def create_project(client: AsyncClient, title: str) -> str:
    response = await client.post("/api/projects", json={"title": title})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_reference_asset_lifecycle_and_metadata(reference_client):
    project_id = await create_project(reference_client, "H3 references")

    uploaded = await reference_client.post(
        f"/api/projects/{project_id}/reference-assets",
        files={"file": ("airframe.png", image_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()
    assert asset["filename"] == "airframe.png"
    assert asset["width"] == 8
    assert asset["height"] == 6
    assert asset["metadata_json"]["reference_kind"] == "equipment_appearance"

    listed = await reference_client.get(f"/api/projects/{project_id}/reference-assets")
    assert [item["id"] for item in listed.json()] == [asset["id"]]
    media = await reference_client.get(asset["url"])
    assert media.status_code == 200
    assert media.content == image_bytes()

    deleted = await reference_client.delete(
        f"/api/projects/{project_id}/reference-assets/{asset['id']}"
    )
    assert deleted.status_code == 204
    assert (await reference_client.get(f"/api/projects/{project_id}/reference-assets")).json() == []
    assert (await reference_client.get(asset["url"])).status_code == 404


@pytest.mark.asyncio
async def test_reference_asset_rejects_non_image_and_oversize_uploads(reference_client):
    project_id = await create_project(reference_client, "Validation")

    fake_image = await reference_client.post(
        f"/api/projects/{project_id}/reference-assets",
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert fake_image.status_code == 400

    oversized = await reference_client.post(
        f"/api/projects/{project_id}/reference-assets",
        files={"file": ("large.png", b"x" * (15 * 1024 * 1024 + 1), "image/png")},
    )
    assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_reference_asset_is_project_owned(reference_client):
    owner_id = await create_project(reference_client, "Owner")
    other_id = await create_project(reference_client, "Other")
    uploaded = await reference_client.post(
        f"/api/projects/{owner_id}/reference-assets",
        files={"file": ("owned.webp", image_bytes("WEBP"), "image/webp")},
    )
    asset_id = uploaded.json()["id"]

    assert (await reference_client.get(f"/api/projects/{other_id}/reference-assets")).json() == []
    assert (
        await reference_client.get(f"/api/projects/{other_id}/reference-assets/{asset_id}/file")
    ).status_code == 404
    assert (
        await reference_client.delete(f"/api/projects/{other_id}/reference-assets/{asset_id}")
    ).status_code == 404
