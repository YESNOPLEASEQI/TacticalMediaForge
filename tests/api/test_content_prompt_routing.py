from types import SimpleNamespace

import pytest

from api.routers import content
from api.schemas.content import ProjectImagePromptGenerateRequest


@pytest.mark.asyncio
async def test_async_storyboard_uses_video_prompt_generator_for_video_assets(monkeypatch):
    generated_with = []
    task_result = {}

    async def fake_create_runtime_job(**_kwargs):
        return True

    async def fake_generate_image_prompts(**_kwargs):
        generated_with.append("image")
        return ["image prompt"]

    async def fake_generate_video_prompts(**_kwargs):
        generated_with.append("video")
        return ["video prompt"]

    async def fake_execute_task(_task_id, execute):
        task_result.update(await execute())

    monkeypatch.setattr(content, "create_runtime_job", fake_create_runtime_job)
    monkeypatch.setattr(content, "generate_image_prompts", fake_generate_image_prompts)
    monkeypatch.setattr(content, "generate_video_prompts", fake_generate_video_prompts, raising=False)
    monkeypatch.setattr(
        content.task_manager,
        "create_task",
        lambda **_kwargs: SimpleNamespace(task_id="storyboard-task"),
    )
    monkeypatch.setattr(content.task_manager, "execute_task", fake_execute_task)

    await content.generate_image_prompt_async(
        ProjectImagePromptGenerateRequest(
            project_id="project-a",
            narrations=["A radar scans the horizon."],
            min_words=30,
            max_words=60,
            asset_type="video",
        ),
        SimpleNamespace(llm=object()),
    )

    assert generated_with == ["video"]
    assert task_result == {"image_prompts": ["video prompt"]}
