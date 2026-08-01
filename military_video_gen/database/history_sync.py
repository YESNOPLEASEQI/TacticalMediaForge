"""Idempotent mapping from legacy JSON history into relational records."""

from __future__ import annotations

import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import (
    ActivityEvent,
    Asset,
    GenerationJob,
    OutputVersion,
    Project,
    ScriptSegment,
    ScriptVersion,
    StoryboardScene,
    StoryboardVersion,
    WorkflowSnapshot,
)
from .session import AsyncSessionFactory, session_scope

HISTORY_NAMESPACE = uuid.UUID("5fd28f5b-6e5f-4f3b-aa90-3847c125e4fa")


def stable_uuid(entity_type: str, *parts: Any) -> str:
    key = ":".join(str(part) for part in parts)
    return str(uuid.uuid5(HISTORY_NAMESPACE, f"{entity_type}:{key}"))


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


class HistoryDatabaseSync:
    """Synchronize one completed filesystem task using a fresh session."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionFactory,
    ) -> None:
        self.session_factory = session_factory

    async def sync_task(
        self,
        task_id: str,
        metadata: dict[str, Any],
        storyboard: Optional[dict[str, Any]] = None,
        *,
        event_type: str = "generation.completed",
    ) -> None:
        for attempt in range(3):
            try:
                async with session_scope(self.session_factory) as session:
                    await self._sync(session, task_id, metadata, storyboard, event_type)
                return
            except IntegrityError:
                if attempt == 2:
                    raise

    async def _sync(
        self,
        session: AsyncSession,
        task_id: str,
        metadata: dict[str, Any],
        storyboard: Optional[dict[str, Any]],
        event_type: str,
    ) -> None:
        input_data = dict(metadata.get("input") or {})
        result_data = dict(metadata.get("result") or {})
        config_data = dict(metadata.get("config") or {})
        created_at = parse_datetime(metadata.get("created_at")) or datetime.now(timezone.utc)
        completed_at = parse_datetime(metadata.get("completed_at"))
        status = str(metadata.get("status") or "completed")

        project = await self._project(session, task_id, input_data, config_data, created_at)
        existing_job = await session.scalar(
            select(GenerationJob).where(
                GenerationJob.provider == "local",
                GenerationJob.external_job_id == task_id,
            )
        )
        script_id = stable_uuid("script", task_id)
        script = await session.get(ScriptVersion, script_id)
        if script is None:
            version_no = await self._next_version(session, ScriptVersion, project.id)
            script = ScriptVersion(id=script_id, project_id=project.id, version_no=version_no)
            session.add(script)
        script.status = "confirmed" if status == "completed" else status
        script.title = input_data.get("title") or project.title
        script.full_text = input_data.get("text") or project.source_text
        script.source = input_data.get("mode") or "legacy_json"
        script.model_name = config_data.get("llm_model")
        script.generation_prompt = input_data.get("generation_prompt")
        script.metadata_json = {"input": input_data, "config": config_data, "task_id": task_id}
        script.created_at = created_at
        script.confirmed_at = completed_at if status == "completed" else None

        job = existing_job
        if job is None:
            job = GenerationJob(
                id=stable_uuid("job", task_id),
                project_id=project.id,
                job_type="video_generation",
                provider="local",
                external_job_id=task_id,
            )
            session.add(job)
        job.script_version_id = script.id
        job.status = status
        job.progress = 100.0 if status == "completed" else 0.0
        job.workflow_id = input_data.get("media_workflow")
        job.model_name = config_data.get("llm_model")
        job.params_json = input_data
        job.result_json = result_data
        job.error_message = metadata.get("error")
        job.created_at = created_at
        job.started_at = created_at
        job.completed_at = completed_at

        final_asset = await self._asset(
            session,
            task_id=task_id,
            project_id=project.id,
            job_id=job.id,
            scene_id=None,
            role="final",
            asset_type="video",
            local_path=result_data.get("video_path"),
            duration=result_data.get("duration"),
            size_bytes=result_data.get("file_size"),
            prompt=None,
            width=input_data.get("media_width"),
            height=input_data.get("media_height"),
            created_at=completed_at or created_at,
        )

        storyboard_version = None
        if storyboard:
            storyboard_version = await self._storyboard(
                session, task_id, project, script, job, storyboard, created_at, completed_at
            )
            job.storyboard_version_id = storyboard_version.id

        output_id = stable_uuid("output", task_id)
        output = await session.get(OutputVersion, output_id)
        if output is None:
            output = OutputVersion(
                id=output_id,
                project_id=project.id,
                version_no=script.version_no,
            )
            session.add(output)
        output.generation_job_id = job.id
        output.storyboard_version_id = storyboard_version.id if storyboard_version else None
        output.status = "approved" if status == "completed" else status
        output.video_asset_id = final_asset.id if final_asset else None
        output.title = project.title
        output.duration = result_data.get("duration")
        output.created_at = completed_at or created_at
        output.approved_at = completed_at if status == "completed" else None

        if status == "completed":
            event_id = stable_uuid("event", event_type, task_id)
            event = await session.get(ActivityEvent, event_id)
            if event is None:
                event = ActivityEvent(
                    id=event_id,
                    project_id=project.id,
                    event_type=event_type,
                )
                session.add(event)
            event.entity_type = "generation_job"
            event.entity_id = job.id
            event.summary = f"Video generation completed for task {task_id}"
            event.payload_json = {"task_id": task_id, "result": result_data}
            event.created_at = completed_at or created_at

        project.status = status
        project.current_stage = "output" if status == "completed" else project.current_stage
        project.updated_at = completed_at or created_at

    async def _project(
        self,
        session: AsyncSession,
        task_id: str,
        input_data: dict[str, Any],
        config_data: dict[str, Any],
        created_at: datetime,
    ) -> Project:
        session_key = str(input_data.get("session_id") or task_id)
        project = None
        try:
            uuid.UUID(session_key)
            project = await session.get(Project, session_key)
        except ValueError:
            pass
        project_id = project.id if project else stable_uuid("project", session_key)
        if project is None:
            project = await session.get(Project, project_id)
        if project is None:
            project = Project(
                id=project_id,
                title=input_data.get("title") or f"Video Session {task_id[:8]}",
                created_at=created_at,
                updated_at=created_at,
            )
            session.add(project)
        if input_data.get("title"):
            project.title = input_data["title"]
        project.project_type = input_data.get("project_type") or "video_agent"
        project.source_text = input_data.get("text") or project.source_text
        project.settings_json = {
            **(project.settings_json or {}),
            "input": {key: value for key, value in input_data.items() if key != "text"},
            "config": config_data,
            "legacy_session_id": session_key,
        }
        return project

    async def _storyboard(
        self,
        session: AsyncSession,
        task_id: str,
        project: Project,
        script: ScriptVersion,
        job: GenerationJob,
        storyboard: dict[str, Any],
        created_at: datetime,
        completed_at: Optional[datetime],
    ) -> StoryboardVersion:
        frames = list(storyboard.get("frames") or [])
        storyboard_id = stable_uuid("storyboard", task_id)
        version = await session.get(StoryboardVersion, storyboard_id)
        if version is None:
            version = StoryboardVersion(
                id=storyboard_id,
                project_id=project.id,
                script_version_id=script.id,
                version_no=script.version_no,
            )
            session.add(version)
        version.status = "confirmed"
        version.title = storyboard.get("title") or project.title
        version.scene_count = len(frames)
        version.total_estimated_duration = storyboard.get("total_duration")
        version.metadata_json = {"config": storyboard.get("config") or {}}
        version.created_at = parse_datetime(storyboard.get("created_at")) or created_at
        version.confirmed_at = parse_datetime(storyboard.get("completed_at")) or completed_at

        narrations = []
        for position, frame in enumerate(frames):
            index = int(frame.get("index", position))
            narration = str(frame.get("narration") or "")
            narrations.append(narration)
            segment_id = stable_uuid("segment", task_id, index)
            segment = await session.get(ScriptSegment, segment_id)
            if segment is None:
                segment = ScriptSegment(
                    id=segment_id,
                    script_version_id=script.id,
                    segment_index=index,
                    narration=narration,
                )
                session.add(segment)
            segment.narration = narration
            segment.estimated_duration = frame.get("estimated_duration") or frame.get("duration")
            segment.metadata_json = {"legacy_frame_index": index}

            scene_id = stable_uuid("scene", task_id, index)
            scene = await session.get(StoryboardScene, scene_id)
            if scene is None:
                scene = StoryboardScene(
                    id=scene_id,
                    storyboard_version_id=version.id,
                    scene_index=index,
                    narration=narration,
                )
                session.add(scene)
            scene.narration = narration
            scene.visual_description = frame.get("visual_description")
            scene.media_prompt = frame.get("media_prompt") or frame.get("image_prompt")
            scene.negative_prompt = frame.get("negative_prompt")
            scene.estimated_duration = frame.get("estimated_duration")
            scene.actual_duration = frame.get("duration")
            scene.asset_type = frame.get("media_type")
            scene.review_status = "confirmed"
            scene.metadata_json = {
                "legacy_frame_index": index,
                **(frame.get("research_metadata") or {}),
            }

            config = storyboard.get("config") or {}
            specs = (
                ("narration_audio", "audio", frame.get("audio_path")),
                ("source_image", "image", frame.get("image_path")),
                ("source_video", "video", frame.get("video_path")),
                ("composed_image", "image", frame.get("composed_image_path")),
                ("segment", "video", frame.get("video_segment_path")),
            )
            for role, asset_type, local_path in specs:
                await self._asset(
                    session,
                    task_id=task_id,
                    project_id=project.id,
                    job_id=job.id,
                    scene_id=scene.id,
                    role=role,
                    asset_type=asset_type,
                    local_path=local_path,
                    duration=frame.get("duration") if asset_type in {"audio", "video"} else None,
                    size_bytes=None,
                    prompt=scene.media_prompt if role in {"source_image", "source_video"} else None,
                    width=config.get("media_width") if asset_type != "audio" else None,
                    height=config.get("media_height") if asset_type != "audio" else None,
                    created_at=parse_datetime(frame.get("created_at")) or created_at,
                )

        if narrations:
            script.full_text = "\n\n".join(item for item in narrations if item)

        workflow_name = (storyboard.get("config") or {}).get("media_workflow")
        if workflow_name:
            snapshot_id = stable_uuid("workflow", task_id, workflow_name)
            snapshot = await session.get(WorkflowSnapshot, snapshot_id)
            if snapshot is None:
                snapshot = WorkflowSnapshot(
                    id=snapshot_id,
                    job_id=job.id,
                    workflow_name=workflow_name,
                )
                session.add(snapshot)
            snapshot.workflow_json = {}
            snapshot.ui_json = {}
            snapshot.config_json = storyboard.get("config") or {}
            snapshot.created_at = created_at
        return version

    async def _asset(
        self,
        session: AsyncSession,
        *,
        task_id: str,
        project_id: str,
        job_id: str,
        scene_id: Optional[str],
        role: str,
        asset_type: str,
        local_path: Optional[str],
        duration: Optional[float],
        size_bytes: Optional[int],
        prompt: Optional[str],
        width: Optional[int],
        height: Optional[int],
        created_at: datetime,
    ) -> Optional[Asset]:
        if not local_path:
            return None
        asset_id = stable_uuid("asset", task_id, role, scene_id or "final", local_path)
        asset = await session.get(Asset, asset_id)
        if asset is None:
            asset = Asset(
                id=asset_id,
                project_id=project_id,
                job_id=job_id,
                storyboard_scene_id=scene_id,
                asset_type=asset_type,
            )
            session.add(asset)
        path = Path(local_path)
        discovered_size = path.stat().st_size if path.is_file() else None
        asset.role = role
        asset.provider = "local"
        asset.local_path = str(local_path)
        asset.filename = path.name
        asset.mime_type = mimetypes.guess_type(path.name)[0]
        asset.size_bytes = size_bytes if size_bytes is not None else discovered_size
        asset.width = width
        asset.height = height
        asset.duration = duration
        asset.prompt = prompt
        asset.metadata_json = {"legacy_task_id": task_id}
        asset.created_at = created_at
        return asset

    @staticmethod
    async def _next_version(session: AsyncSession, model, project_id: str) -> int:
        current = await session.scalar(
            select(func.max(model.version_no)).where(model.project_id == project_id)
        )
        return int(current or 0) + 1
