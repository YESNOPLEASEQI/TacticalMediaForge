"""Project-owned visual reference asset endpoints."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.projects import ReferenceAssetRead
from military_video_gen.database.models import Asset, Project, utcnow
from military_video_gen.database.session import get_db_session
from military_video_gen.utils.os_util import get_data_path

router = APIRouter(prefix="/projects", tags=["Project Reference Assets"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
MAX_REFERENCE_BYTES = 15 * 1024 * 1024
ALLOWED_FORMATS = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
}


async def _active_project(project_id: str, session: AsyncSession) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _reference_root(project_id: str) -> Path:
    return Path(get_data_path("projects", project_id, "references")).resolve()


def _owned_reference_path(asset: Asset) -> Path:
    if asset.role != "visual_reference" or not asset.local_path:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    root = _reference_root(asset.project_id)
    candidate = Path(asset.local_path).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=403, detail="Reference asset path is invalid")
    return candidate


def _asset_response(request: Request, asset: Asset) -> ReferenceAssetRead:
    return ReferenceAssetRead(
        id=asset.id,
        project_id=asset.project_id,
        filename=asset.filename or "reference",
        mime_type=asset.mime_type or "application/octet-stream",
        size_bytes=int(asset.size_bytes or 0),
        width=int(asset.width or 0),
        height=int(asset.height or 0),
        metadata_json=asset.metadata_json or {},
        url=(
            f"{str(request.base_url).rstrip('/')}/api/projects/"
            f"{asset.project_id}/reference-assets/{asset.id}/file"
        ),
        created_at=asset.created_at,
    )


@router.post(
    "/{project_id}/reference-assets",
    response_model=ReferenceAssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reference_asset(
    project_id: str,
    request: Request,
    session: DBSession,
    file: UploadFile = File(...),
):
    """Decode and persist one project-owned PNG/JPEG/WEBP reference image."""
    project = await _active_project(project_id, session)
    contents = await file.read(MAX_REFERENCE_BYTES + 1)
    if len(contents) > MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=413, detail="Reference image exceeds the 15 MB limit")
    if not contents:
        raise HTTPException(status_code=400, detail="Reference image is empty")

    try:
        with Image.open(io.BytesIO(contents)) as image:
            image.load()
            image_format = (image.format or "").upper()
            width, height = image.size
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Reference image cannot be decoded") from exc

    format_info = ALLOWED_FORMATS.get(image_format)
    if format_info is None:
        raise HTTPException(status_code=415, detail="Only PNG, JPEG, and WEBP images are supported")

    extension, mime_type = format_info
    asset_id = str(uuid4())
    root = _reference_root(project.id)
    root.mkdir(parents=True, exist_ok=True)
    local_path = root / f"{asset_id}{extension}"
    local_path.write_bytes(contents)

    original_name = Path(file.filename or f"reference{extension}").name
    asset = Asset(
        id=asset_id,
        project_id=project.id,
        asset_type="image",
        role="visual_reference",
        provider="local",
        local_path=str(local_path),
        filename=original_name,
        mime_type=mime_type,
        size_bytes=len(contents),
        width=width,
        height=height,
        metadata_json={
            "reference_kind": "equipment_appearance",
            "label": original_name,
        },
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return _asset_response(request, asset)


@router.get("/{project_id}/reference-assets", response_model=list[ReferenceAssetRead])
async def list_reference_assets(project_id: str, request: Request, session: DBSession):
    """List active visual reference images belonging to a project."""
    project = await _active_project(project_id, session)
    assets = list(
        (
            await session.scalars(
                select(Asset)
                .where(
                    Asset.project_id == project.id,
                    Asset.asset_type == "image",
                    Asset.role == "visual_reference",
                    Asset.deleted_at.is_(None),
                )
                .order_by(Asset.created_at.asc())
            )
        ).all()
    )
    return [_asset_response(request, asset) for asset in assets]


@router.get("/{project_id}/reference-assets/{asset_id}/file")
async def get_reference_asset_file(project_id: str, asset_id: str, session: DBSession):
    """Serve a project-owned reference image through its dedicated endpoint."""
    await _active_project(project_id, session)
    asset = await session.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.project_id == project_id,
            Asset.asset_type == "image",
            Asset.role == "visual_reference",
            Asset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    local_path = _owned_reference_path(asset)
    if not local_path.is_file():
        raise HTTPException(status_code=404, detail="Reference asset file not found")
    return FileResponse(
        path=str(local_path),
        media_type=asset.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{local_path.name}"'},
    )


@router.delete("/{project_id}/reference-assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reference_asset(project_id: str, asset_id: str, session: DBSession):
    """Soft-delete a reference asset and remove only its dedicated file."""
    await _active_project(project_id, session)
    asset = await session.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.project_id == project_id,
            Asset.role == "visual_reference",
        )
    )
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Reference asset not found")
    local_path = _owned_reference_path(asset)
    if local_path.exists():
        if not local_path.is_file():
            raise HTTPException(status_code=403, detail="Reference asset path is invalid")
        local_path.unlink()
    asset.deleted_at = utcnow()
    await session.commit()
