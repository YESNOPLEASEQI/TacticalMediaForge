"""First-version relational persistence models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, new_uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_status_created_at", "status", "created_at"),
        Index("ix_projects_type_created_at", "project_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(String(50), default="video_agent", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(String(50))
    source_text: Mapped[Optional[str]] = mapped_column(Text)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text)
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    script_versions: Mapped[list[ScriptVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")
    storyboard_versions: Mapped[list[StoryboardVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")
    generation_jobs: Mapped[list[GenerationJob]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list[Asset]] = relationship(back_populates="project", cascade="all, delete-orphan")
    output_versions: Mapped[list[OutputVersion]] = relationship(back_populates="project", cascade="all, delete-orphan")
    activity_events: Mapped[list[ActivityEvent]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_script_versions_project_version"),
        Index("ix_script_versions_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    full_text: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    model_name: Mapped[Optional[str]] = mapped_column(String(255))
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="script_versions")
    segments: Mapped[list[ScriptSegment]] = relationship(back_populates="script_version", cascade="all, delete-orphan")
    storyboard_versions: Mapped[list[StoryboardVersion]] = relationship(back_populates="script_version")
    generation_jobs: Mapped[list[GenerationJob]] = relationship(back_populates="script_version")


class ScriptSegment(Base):
    __tablename__ = "script_segments"
    __table_args__ = (
        UniqueConstraint("script_version_id", "segment_index", name="uq_script_segments_version_index"),
        Index("ix_script_segments_version_id", "script_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    script_version_id: Mapped[str] = mapped_column(ForeignKey("script_versions.id", ondelete="CASCADE"), nullable=False)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    script_version: Mapped[ScriptVersion] = relationship(back_populates="segments")


class StoryboardVersion(Base):
    __tablename__ = "storyboard_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_storyboard_versions_project_version"),
        Index("ix_storyboard_versions_project_id", "project_id"),
        Index("ix_storyboard_versions_script_version_id", "script_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    script_version_id: Mapped[str] = mapped_column(ForeignKey("script_versions.id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    scene_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_estimated_duration: Mapped[Optional[float]] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="storyboard_versions")
    script_version: Mapped[ScriptVersion] = relationship(back_populates="storyboard_versions")
    scenes: Mapped[list[StoryboardScene]] = relationship(back_populates="storyboard_version", cascade="all, delete-orphan")
    generation_jobs: Mapped[list[GenerationJob]] = relationship(back_populates="storyboard_version")
    output_versions: Mapped[list[OutputVersion]] = relationship(back_populates="storyboard_version")


class StoryboardScene(Base):
    __tablename__ = "storyboard_scenes"
    __table_args__ = (
        UniqueConstraint("storyboard_version_id", "scene_index", name="uq_storyboard_scenes_version_index"),
        Index("ix_storyboard_scenes_version_id", "storyboard_version_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    storyboard_version_id: Mapped[str] = mapped_column(ForeignKey("storyboard_versions.id", ondelete="CASCADE"), nullable=False)
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    visual_description: Mapped[Optional[str]] = mapped_column(Text)
    media_prompt: Mapped[Optional[str]] = mapped_column(Text)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text)
    estimated_duration: Mapped[Optional[float]] = mapped_column(Float)
    actual_duration: Mapped[Optional[float]] = mapped_column(Float)
    asset_type: Mapped[Optional[str]] = mapped_column(String(50))
    review_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    storyboard_version: Mapped[StoryboardVersion] = relationship(back_populates="scenes")
    assets: Mapped[list[Asset]] = relationship(back_populates="storyboard_scene")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint("provider", "external_job_id", name="uq_generation_jobs_provider_external"),
        Index("ix_generation_jobs_project_status", "project_id", "status"),
        Index("ix_generation_jobs_parent_job_id", "parent_job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    script_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("script_versions.id", ondelete="SET NULL"))
    storyboard_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("storyboard_versions.id", ondelete="SET NULL"))
    parent_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), default="local", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    external_job_id: Mapped[Optional[str]] = mapped_column(String(255))
    workflow_id: Mapped[Optional[str]] = mapped_column(String(255))
    model_name: Mapped[Optional[str]] = mapped_column(String(255))
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="generation_jobs")
    script_version: Mapped[Optional[ScriptVersion]] = relationship(back_populates="generation_jobs")
    storyboard_version: Mapped[Optional[StoryboardVersion]] = relationship(back_populates="generation_jobs")
    parent_job: Mapped[Optional[GenerationJob]] = relationship(remote_side="GenerationJob.id", back_populates="child_jobs")
    child_jobs: Mapped[list[GenerationJob]] = relationship(back_populates="parent_job")
    assets: Mapped[list[Asset]] = relationship(back_populates="job")
    workflow_snapshots: Mapped[list[WorkflowSnapshot]] = relationship(back_populates="job", cascade="all, delete-orphan")
    output_versions: Mapped[list[OutputVersion]] = relationship(back_populates="generation_job")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("job_id", "role", "local_path", name="uq_assets_job_role_path"),
        Index("ix_assets_project_type", "project_id", "asset_type"),
        Index("ix_assets_job_id", "job_id"),
        Index("ix_assets_storyboard_scene_id", "storyboard_scene_id"),
        Index("ix_assets_local_path", "local_path"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    storyboard_scene_id: Mapped[Optional[str]] = mapped_column(ForeignKey("storyboard_scenes.id", ondelete="SET NULL"))
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100))
    provider: Mapped[Optional[str]] = mapped_column(String(100))
    local_path: Mapped[Optional[str]] = mapped_column(Text)
    remote_url: Mapped[Optional[str]] = mapped_column(Text)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text)
    filename: Mapped[Optional[str]] = mapped_column(String(512))
    mime_type: Mapped[Optional[str]] = mapped_column(String(255))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    duration: Mapped[Optional[float]] = mapped_column(Float)
    prompt: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="assets")
    job: Mapped[Optional[GenerationJob]] = relationship(back_populates="assets")
    storyboard_scene: Mapped[Optional[StoryboardScene]] = relationship(back_populates="assets")
    output_versions: Mapped[list[OutputVersion]] = relationship(back_populates="video_asset")


class WorkflowSnapshot(Base):
    __tablename__ = "workflow_snapshots"
    __table_args__ = (Index("ix_workflow_snapshots_job_id", "job_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ui_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    job: Mapped[GenerationJob] = relationship(back_populates="workflow_snapshots")


class OutputVersion(Base):
    __tablename__ = "output_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_no", name="uq_output_versions_project_version"),
        Index("ix_output_versions_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generation_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id", ondelete="SET NULL"))
    storyboard_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("storyboard_versions.id", ondelete="SET NULL"))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    video_asset_id: Mapped[Optional[str]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    duration: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="output_versions")
    generation_job: Mapped[Optional[GenerationJob]] = relationship(back_populates="output_versions")
    storyboard_version: Mapped[Optional[StoryboardVersion]] = relationship(back_populates="output_versions")
    video_asset: Mapped[Optional[Asset]] = relationship(back_populates="output_versions")


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_events_project_created_at", "project_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    actor_id: Mapped[Optional[str]] = mapped_column(String(36))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="activity_events")
