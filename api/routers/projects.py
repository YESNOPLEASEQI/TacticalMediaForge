"""Minimal project management API."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from military_video_gen.database.models import Project, utcnow
from military_video_gen.database.session import get_db_session
from military_video_gen.prompts.legacy_contract import clean_project_settings

router = APIRouter(prefix="/projects", tags=["Projects"])
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def _active_project(session: AsyncSession, project_id: str) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    session: DBSession,
    project_status: Optional[str] = Query(default=None, alias="status"),
    project_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    statement = select(Project).where(Project.deleted_at.is_(None))
    if project_status:
        statement = statement.where(Project.status == project_status)
    if project_type:
        statement = statement.where(Project.project_type == project_type)
    statement = statement.order_by(Project.updated_at.desc()).offset(offset).limit(limit)
    return list((await session.scalars(statement)).all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, session: DBSession):
    values = payload.model_dump()
    values["settings_json"], _ = clean_project_settings(values.get("settings_json") or {})
    project = Project(**values)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, session: DBSession):
    return await _active_project(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(project_id: str, payload: ProjectUpdate, session: DBSession):
    project = await _active_project(session, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "settings_json" and value is not None:
            merged = {**(project.settings_json or {}), **value}
            project.settings_json, _ = clean_project_settings(merged)
        else:
            setattr(project, field, value)
    project.updated_at = utcnow()
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, session: DBSession):
    project = await _active_project(session, project_id)
    project.deleted_at = utcnow()
    project.updated_at = project.deleted_at
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
