import pytest
from pydantic import ValidationError

from api.routers.history import resolve_latest_task_id
from api.schemas.video import VideoGenerateRequest
from military_video_gen.models.storyboard import StoryboardFrame
from military_video_gen.pipelines.linear import PipelineContext
from military_video_gen.pipelines.standard import StandardPipeline
from military_video_gen.services.persistence import PersistenceService


class FakePersistence:
    def __init__(self):
        self.metadata = {
            "session-a": {
                "task_id": "session-a",
                "created_at": "2026-07-01T00:00:00",
                "status": "completed",
                "input": {"text": "old"},
            },
            "task-b": {
                "task_id": "task-b",
                "created_at": "2026-07-02T00:00:00",
                "status": "completed",
                "input": {"text": "new", "session_id": "session-a"},
            },
        }

    async def list_tasks(self, **_kwargs):
        return [{"task_id": "task-b"}, {"task_id": "session-a"}]

    async def load_task_metadata(self, task_id):
        return self.metadata.get(task_id)


def test_video_request_accepts_confirmed_storyboard():
    request = VideoGenerateRequest(
        text="段落一",
        mode="fixed",
        frame_template="1080x1920/video_default.html",
        session_id="existing-session",
        confirmed_storyboard=[
            {
                "index": 0,
                "narration": "段落一",
                "visual_description": "雷达阵列",
                "media_prompt": "cinematic radar array",
                "estimated_duration": 4,
                "asset_type": "video",
            }
        ],
    )

    assert request.session_id == "existing-session"
    assert request.confirmed_storyboard is not None
    assert request.confirmed_storyboard[0].narration == "段落一"
    assert request.confirmed_storyboard[0].media_prompt == "cinematic radar array"


def test_video_request_rejects_chinese_media_prompt() -> None:
    with pytest.raises(ValidationError, match="English text only"):
        VideoGenerateRequest(
            text="段落一",
            mode="fixed",
            confirmed_storyboard=[
                {
                    "index": 0,
                    "narration": "段落一",
                    "media_prompt": "雷达阵列 cinematic view",
                }
            ],
        )


def test_video_request_rejects_chinese_legacy_visual_fallback() -> None:
    with pytest.raises(ValidationError, match="English text only"):
        VideoGenerateRequest(
            text="段落一",
            mode="fixed",
            confirmed_storyboard=[
                {
                    "index": 0,
                    "narration": "段落一",
                    "visual_description": "旧版中文画面提示",
                    "media_prompt": "",
                }
            ],
        )


def test_video_request_rejects_old_unanchored_fallback_prompt() -> None:
    with pytest.raises(ValidationError, match="concrete subject"):
        VideoGenerateRequest(
            text="段落一",
            mode="fixed",
            confirmed_storyboard=[
                {
                    "index": 0,
                    "narration": "段落一",
                    "media_prompt": (
                        "A restrained wide establishing view introduces a credible "
                        "military technology subject in an ordinary environment."
                    ),
                }
            ],
        )


def test_video_request_rejects_retired_non_identifying_prompt() -> None:
    with pytest.raises(ValidationError, match="retired prompt contract"):
        VideoGenerateRequest(
            text="tank",
            mode="fixed",
            confirmed_storyboard=[
                {
                    "index": 0,
                    "narration": "tank",
                    "media_prompt": (
                        "A non-identifying main battle tank remains at rest with neutral "
                        "markings in a generic military environment."
                    ),
                }
            ],
        )


def test_video_request_rejects_duplicate_confirmed_prompts() -> None:
    with pytest.raises(ValidationError, match="prompts must be unique"):
        VideoGenerateRequest(
            text="two scenes",
            mode="fixed",
            confirmed_storyboard=[
                {"index": 0, "narration": "one", "media_prompt": "A tank crosses mud."},
                {"index": 1, "narration": "two", "media_prompt": "  a tank crosses   mud. "},
            ],
        )


def test_video_request_preserves_research_provenance_fields():
    request = VideoGenerateRequest(
        text="verified",
        mode="fixed",
        verification_mode="verified",
        research_topic="aircraft",
        script_revision=2,
        session_id="project-a",
        frame_template="1080x1920/video_default.html",
        confirmed_storyboard=[
            {
                "index": 1,
                "narration": "verified",
                "research_job_id": "research-1",
                "claim_ids": ["claim-1"],
                "visual_fact_ids": ["visual-1"],
                "field_provenance": {
                    "subject": {"visual_fact_ids": ["visual-1"]}
                },
                "verification_status": "verified",
                "fallback_level": "verified_generic",
            }
        ],
    )

    scene = request.confirmed_storyboard[0]
    assert scene.research_job_id == "research-1"
    assert scene.field_provenance["subject"].visual_fact_ids == ["visual-1"]


def test_video_request_accepts_empty_generic_provenance() -> None:
    request = VideoGenerateRequest(
        text="generic",
        mode="fixed",
        verification_mode="verified",
        confirmed_storyboard=[
            {
                "index": 0,
                "narration": "generic",
                "media_prompt": "generic military technology display",
                "field_provenance": {
                    "subject": {
                        "claim_ids": [],
                        "visual_fact_ids": [],
                        "creative": False,
                    }
                },
                "verification_status": "partial",
                "fallback_level": "generic_safe",
            }
        ],
    )

    assert request.confirmed_storyboard[0].field_provenance["subject"].creative is False


@pytest.mark.asyncio
async def test_pipeline_uses_confirmed_storyboard_without_llm():
    context = PipelineContext(
        input_text="legacy text",
        params={
            "confirmed_storyboard": [
                {
                    "index": 0,
                    "narration": "确认旁白",
                    "visual_description": "确认画面",
                    "media_prompt": "confirmed prompt",
                    "estimated_duration": 5,
                    "asset_type": "video",
                }
            ]
        },
    )
    pipeline = object.__new__(StandardPipeline)

    await pipeline.generate_content(context)
    await pipeline.plan_visuals(context)

    assert context.narrations == ["确认旁白"]
    assert context.image_prompts == ["confirmed prompt"]


@pytest.mark.asyncio
async def test_pipeline_ignores_blank_confirmed_scenes():
    context = PipelineContext(
        input_text="legacy text",
        params={
            "confirmed_storyboard": [
                {"index": 0, "narration": "", "media_prompt": "unused"},
                {"index": 1, "narration": "有效旁白", "media_prompt": "kept"},
            ]
        },
    )
    pipeline = object.__new__(StandardPipeline)

    await pipeline.generate_content(context)
    await pipeline.plan_visuals(context)

    assert context.narrations == ["有效旁白"]
    assert context.image_prompts == ["kept"]


@pytest.mark.asyncio
async def test_pipeline_generates_only_missing_confirmed_prompts(monkeypatch):
    generated_for = []

    async def fake_generate_video_prompts(*_args, **kwargs):
        generated_for.extend(kwargs["narrations"])
        return ["generated missing prompt"]

    monkeypatch.setattr(
        "military_video_gen.pipelines.standard.generate_video_prompts",
        fake_generate_video_prompts,
    )
    context = PipelineContext(
        input_text="legacy text",
        params={
            "frame_template": "1080x1920/video_default.html",
            "media_workflow": "selfhost/video_ltx2_3_t2v.json",
            "confirmed_storyboard": [
                {
                    "index": 0,
                    "narration": "第一段旁白",
                    "media_prompt": "kept confirmed prompt",
                    "asset_type": "video",
                },
                {
                    "index": 1,
                    "narration": "第二段旁白",
                    "media_prompt": "",
                    "asset_type": "video",
                },
            ],
        },
    )
    pipeline = object.__new__(StandardPipeline)
    pipeline.llm = object()
    pipeline.core = type("Core", (), {"config": {"comfyui": {"video": {}}}})()

    await pipeline.generate_content(context)
    await pipeline.plan_visuals(context)

    assert generated_for == ["第二段旁白"]
    assert context.image_prompts == [
        "kept confirmed prompt",
        "generated missing prompt",
    ]


def test_storyboard_persistence_preserves_editable_scene_metadata():
    frame = StoryboardFrame(
        index=0,
        narration="确认旁白",
        image_prompt="confirmed prompt",
        visual_description="独立画面描述",
        estimated_duration=4.5,
        media_type="video",
    )
    persistence = object.__new__(PersistenceService)

    restored = persistence._dict_to_frame(persistence._frame_to_dict(frame))

    assert restored.visual_description == "独立画面描述"
    assert restored.estimated_duration == 4.5
    assert restored.media_type == "video"


def test_storyboard_persistence_preserves_research_metadata():
    frame = StoryboardFrame(
        index=0,
        narration="verified",
        image_prompt="audited prompt",
        research_metadata={
            "research_job_id": "research-1",
            "claim_ids": ["claim-1"],
            "field_provenance": {
                "subject": {"visual_fact_ids": ["visual-1"]}
            },
        },
    )
    persistence = object.__new__(PersistenceService)

    restored = persistence._dict_to_frame(persistence._frame_to_dict(frame))

    assert restored.research_metadata == frame.research_metadata


@pytest.mark.asyncio
async def test_history_session_resolves_to_latest_continued_task(monkeypatch):
    monkeypatch.setattr("api.routers.history.task_manager.list_tasks", lambda **_kwargs: [])
    service = type("Service", (), {"persistence": FakePersistence()})()

    assert await resolve_latest_task_id(service, "session-a") == "task-b"
