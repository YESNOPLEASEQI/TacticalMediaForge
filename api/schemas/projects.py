"""Project CRUD request and response schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: str = "video_agent"
    status: str = "draft"
    current_stage: Optional[str] = None
    source_text: Optional[str] = None
    thumbnail_path: Optional[str] = None
    owner_id: Optional[str] = None
    settings_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    current_stage: Optional[str] = None
    source_text: Optional[str] = None
    thumbnail_path: Optional[str] = None
    owner_id: Optional[str] = None
    settings_json: Optional[dict[str, Any]] = None
    archived_at: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: Optional[str]
    project_type: str
    status: str
    current_stage: Optional[str]
    source_text: Optional[str]
    thumbnail_path: Optional[str]
    owner_id: Optional[str]
    settings_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime]
    deleted_at: Optional[datetime]


class ReferenceAssetRead(BaseModel):
    """Project-owned visual reference image returned by the reference library."""

    id: str
    project_id: str
    filename: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    metadata_json: dict[str, Any]
    url: str
    created_at: datetime
