import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from military_video_gen.database.base import Base
from military_video_gen.database.history_sync import HistoryDatabaseSync
from military_video_gen.database.models import (
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
from military_video_gen.database.session import create_engine
from military_video_gen.models.storyboard import Storyboard, StoryboardConfig, StoryboardFrame
from military_video_gen.services.persistence import PersistenceService


def sample_metadata(task_id="task-1"):
    return {
        "task_id": task_id,
        "created_at": "2026-07-14T01:00:00",
        "completed_at": "2026-07-14T01:05:00",
        "status": "completed",
        "input": {
            "session_id": "session-1",
            "title": "Test project",
            "text": "source text",
            "mode": "generate",
            "media_workflow": "selfhost/video.json",
        },
        "result": {"video_path": "output/task-1/final.mp4", "duration": 9.5, "file_size": 42},
        "config": {"llm_model": "model-a"},
    }


def sample_storyboard():
    return {
        "title": "Test project",
        "config": {"media_width": 1920, "media_height": 1080, "media_workflow": "selfhost/video.json"},
        "frames": [
            {
                "index": 0,
                "narration": "first",
                "visual_description": "radar",
                "image_prompt": "prompt one",
                "audio_path": "output/task-1/frames/01_audio.mp3",
                "video_path": "output/task-1/frames/01_video.mp4",
                "duration": 4.0,
            },
            {
                "index": 1,
                "narration": "second",
                "image_prompt": "prompt two",
                "video_segment_path": "output/task-1/frames/02_segment.mp4",
                "duration": 5.5,
            },
        ],
        "total_duration": 9.5,
    }


@pytest.mark.asyncio
async def test_history_sync_builds_complete_idempotent_graph(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'history.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sync = HistoryDatabaseSync(factory)
    await sync.sync_task("task-1", sample_metadata(), sample_storyboard())
    await sync.sync_task("task-1", sample_metadata(), sample_storyboard())

    expected = {
        Project: 1,
        ScriptVersion: 1,
        ScriptSegment: 2,
        StoryboardVersion: 1,
        StoryboardScene: 2,
        GenerationJob: 1,
        Asset: 4,
        WorkflowSnapshot: 1,
        OutputVersion: 1,
        ActivityEvent: 1,
    }
    async with factory() as session:
        for model, count in expected.items():
            assert await session.scalar(select(func.count()).select_from(model)) == count
        project = await session.scalar(select(Project))
        job = await session.scalar(select(GenerationJob))
        output = await session.scalar(select(OutputVersion))
        assert project.title == "Test project"
        assert job.external_job_id == "task-1"
        assert job.script_version_id is not None
        assert job.storyboard_version_id is not None
        assert output.video_asset_id is not None

    await engine.dispose()


class FailingDatabaseSync:
    async def sync_task(self, *_args, **_kwargs):
        raise RuntimeError("database unavailable")


@pytest.mark.asyncio
async def test_json_save_succeeds_when_database_sync_fails(tmp_path):
    persistence = PersistenceService(output_dir=str(tmp_path), database_sync=FailingDatabaseSync())
    metadata = sample_metadata("task-failure")

    await persistence.save_task_metadata("task-failure", metadata)
    storyboard = Storyboard(
        title="Still saved",
        config=StoryboardConfig(media_width=1920, media_height=1080, task_id="task-failure"),
        frames=[StoryboardFrame(index=0, narration="narration", image_prompt="prompt")],
    )
    await persistence.save_storyboard("task-failure", storyboard)

    assert Path(tmp_path, "task-failure", "metadata.json").exists()
    assert Path(tmp_path, "task-failure", "storyboard.json").exists()


@pytest.mark.asyncio
async def test_history_sync_preserves_database_workspace_draft(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'draft.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    project_id = str(uuid.uuid4())
    async with factory() as session:
        session.add(
            Project(
                id=project_id,
                title="Draft project",
                settings_json={"workspace_draft": {"version": 1, "title": "Saved draft"}},
            )
        )
        await session.commit()

    metadata = sample_metadata("task-for-project")
    metadata["input"]["session_id"] = project_id
    await HistoryDatabaseSync(factory).sync_task("task-for-project", metadata, sample_storyboard())

    async with factory() as session:
        stored = await session.get(Project, project_id)
        assert stored.settings_json["workspace_draft"]["title"] == "Saved draft"

    await engine.dispose()
