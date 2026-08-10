import asyncio

import pytest

from api.tasks.manager import TaskManager
from api.tasks.models import TaskStatus, TaskType


@pytest.mark.asyncio
async def test_execute_task_uses_per_task_timeout_override():
    manager = TaskManager(task_timeout_seconds=10)
    task = manager.create_task(TaskType.VIDEO_GENERATION)

    async def never_finishes():
        await asyncio.sleep(1)
        return {"ok": True}

    await manager.execute_task(
        task.task_id,
        never_finishes,
        timeout_seconds=0.01,
    )
    future = manager._task_futures[task.task_id]
    await asyncio.gather(future, return_exceptions=True)

    assert task.status == TaskStatus.FAILED
    assert task.error == "Task timed out after 0.01 seconds"


def test_progress_keeps_real_scene_coordinates():
    manager = TaskManager()
    task = manager.create_task(TaskType.VIDEO_GENERATION)

    manager.update_progress(
        task.task_id,
        current=2500,
        total=10000,
        message="生成视觉素材",
        stage="media",
        current_scene=2,
        total_scenes=5,
    )

    assert task.progress is not None
    assert task.progress.percentage == 25
    assert task.progress.current_scene == 2
    assert task.progress.total_scenes == 5
