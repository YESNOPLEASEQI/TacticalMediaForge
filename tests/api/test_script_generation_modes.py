from types import SimpleNamespace

import pytest

from api.routers import content
from api.schemas.content import NarrationGenerateRequest, ProjectNarrationGenerateRequest


def test_script_api_defaults_to_quick_mode():
    assert NarrationGenerateRequest(text="radar").mode == "quick"


async def _run_script_job(monkeypatch, *, mode: str):
    task_result = {}
    calls = []

    async def fake_create_runtime_job(**_kwargs):
        return True

    async def fake_quick(**_kwargs):
        calls.append("quick")
        return ["quick script"]

    async def fake_reference(**_kwargs):
        calls.append("reference")
        calls.append(f"require_references={_kwargs.get('require_references')}")
        return SimpleNamespace(
            narrations=["referenced script"],
            research_status="reference_ready",
            queries=["radar history"],
            sources=[{"title": "source", "url": "https://example.com"}],
        )

    async def fake_execute_task(_task_id, execute):
        task_result.update(await execute())

    monkeypatch.setattr(content, "create_runtime_job", fake_create_runtime_job)
    monkeypatch.setattr(content, "generate_narrations_from_topic", fake_quick)
    monkeypatch.setattr(content, "generate_researched_narrations", fake_reference)
    monkeypatch.setattr(
        content.task_manager,
        "create_or_get_task",
        lambda **_kwargs: (SimpleNamespace(task_id="script-task"), True),
    )
    monkeypatch.setattr(content.task_manager, "execute_task", fake_execute_task)

    await content.generate_narration_async(
        ProjectNarrationGenerateRequest(
            project_id="project-a",
            text="radar",
            n_scenes=1,
            mode=mode,
        ),
        SimpleNamespace(llm=object()),
    )
    return calls, task_result


@pytest.mark.asyncio
async def test_quick_script_mode_skips_online_research(monkeypatch):
    calls, result = await _run_script_job(monkeypatch, mode="quick")

    assert calls == ["quick"]
    assert result == {
        "narrations": ["quick script"],
        "research_status": "quick",
        "queries": [],
        "sources": [],
    }


@pytest.mark.asyncio
async def test_reference_script_mode_uses_online_research(monkeypatch):
    calls, result = await _run_script_job(monkeypatch, mode="reference")

    assert calls == ["reference", "require_references=False"]
    assert result["narrations"] == ["referenced script"]
    assert result["research_status"] == "reference_ready"
    assert result["queries"] == ["radar history"]
