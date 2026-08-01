import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.schemas.content import ProjectImagePromptGenerateRequest
from military_video_gen.prompts.video_generation import (
    build_video_prompt_prompt,
    video_prompt_word_range,
)
from military_video_gen.utils.content_generators import (
    _parse_json,
    generate_video_prompts,
)


def words(label: str, count: int) -> str:
    return " ".join([label] * count)


def test_duration_aware_video_prompt_word_ranges() -> None:
    assert video_prompt_word_range(3) == (40, 100)
    assert video_prompt_word_range(6) == (60, 140)
    assert video_prompt_word_range(12) == (90, 170)
    assert video_prompt_word_range(20) == (110, 195)


def test_video_prompt_input_separates_narration_references_and_duration() -> None:
    prompt = build_video_prompt_prompt(
        ["雷达天线开始旋转"],
        estimated_durations=[6],
        reference_contexts=[["The antenna rotates at a steady rate."]],
    )

    assert '"narration": "雷达天线开始旋转"' in prompt
    assert '"estimated_duration_seconds": 6' in prompt
    assert '"min": 60' in prompt
    assert '"max": 140' in prompt
    assert '"reference_notes": [' in prompt
    assert "Never anonymize a subject merely" in prompt
    assert "events chronologically in present tense" in prompt
    assert "synchronized environmental or mechanical sound" in prompt
    assert "never exceed 200 English words" in prompt


def test_json_fallback_accepts_unfenced_video_prompts() -> None:
    result = _parse_json('Here is the JSON: {"video_prompts": ["one prompt"]}')

    assert result == {"video_prompts": ["one prompt"]}


def test_storyboard_asset_type_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        ProjectImagePromptGenerateRequest(
            project_id="project-a",
            narrations=["narration"],
            asset_type="ltx",
        )


async def test_video_prompt_generation_retries_only_invalid_scenes() -> None:
    valid_first = words("observation", 55)
    valid_second = words("tracking", 55)

    class RepairingLLM:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        async def __call__(self, **kwargs):
            self.prompts.append(kwargs["prompt"])
            if len(self.prompts) == 1:
                return json.dumps({"video_prompts": [valid_first, "short prompt"]})
            return json.dumps({"video_prompts": [valid_second]})

    llm = RepairingLLM()
    result = await generate_video_prompts(
        llm,
        ["scene one", "scene two"],
        estimated_durations=[3, 3],
        max_retries=2,
    )

    assert result == [valid_first, valid_second]
    assert len(llm.prompts) == 2
    assert llm.prompts[1].count('"narration"') == 1
    assert "use at least 40 English words" in llm.prompts[1]


async def test_video_prompt_validation_never_blocks_usable_output() -> None:
    class ShortPromptLLM:
        async def __call__(self, **_kwargs):
            return json.dumps({"video_prompts": ["short but usable prompt"]})

    result = await generate_video_prompts(
        ShortPromptLLM(),
        ["scene"],
        estimated_durations=[3],
        max_retries=2,
    )

    assert result == ["short but usable prompt"]


async def test_video_prompt_generation_repairs_chinese_output() -> None:
    english_prompt = words("tracking", 55)

    class RepairingLanguageLLM:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def __call__(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return json.dumps({"video_prompts": ["雷达天线缓慢旋转"]})
            return json.dumps({"video_prompts": [english_prompt]})

    llm = RepairingLanguageLLM()
    result = await generate_video_prompts(
        llm,
        ["雷达开始工作"],
        estimated_durations=[3],
        max_retries=2,
        model="deepseek-v4-flash",
    )

    assert result == [english_prompt]
    assert "use English only; remove all CJK characters" in llm.calls[1]["prompt"]
    assert all(call["model"] == "deepseek-v4-flash" for call in llm.calls)
    assert all(call["max_tokens"] == 3072 for call in llm.calls)


async def test_video_prompt_generation_rejects_persistent_chinese_output() -> None:
    class ChinesePromptLLM:
        async def __call__(self, **_kwargs):
            return json.dumps({"video_prompts": ["中文分镜提示词"]})

    with pytest.raises(ValueError, match="English-only"):
        await generate_video_prompts(
            ChinesePromptLLM(),
            ["旁白"],
            estimated_durations=[3],
            max_retries=2,
        )


async def test_video_prompt_generation_allows_public_military_specificity() -> None:
    specific_prompt = (
        "Medium view of a muzzle-loading cannon as a gun crew loads the barrel "
        + words("detail", 55)
    )

    class SpecificityLLM:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def __call__(self, **kwargs):
            self.calls.append(kwargs)
            return json.dumps({"video_prompts": [specific_prompt]})

    llm = SpecificityLLM()
    result = await generate_video_prompts(
        llm,
        ["大炮发射弹丸"],
        estimated_durations=[3],
        max_retries=2,
    )

    assert result == [specific_prompt]
    assert len(llm.calls) == 1


async def test_video_prompt_generation_does_not_fact_police_visible_mechanisms() -> None:
    procedural = (
        "Close view of a nineteenth-century cannon as a rifling machine drives a "
        "cutting tool through the barrel and begins carving a spiral groove " + words("detail", 55)
    )

    class ProceduralLLM:
        async def __call__(self, **_kwargs):
            return json.dumps({"video_prompts": [procedural]})

    result = await generate_video_prompts(
        ProceduralLLM(),
        ["人们在炮管内刻上螺旋膛线，让弹丸旋转着飞出"],
        estimated_durations=[6],
        max_retries=2,
    )

    assert result == [procedural]


def test_ltx_prompt_enhancement_is_disabled() -> None:
    workflow_path = Path(__file__).parents[1] / "workflows" / "selfhost" / "video_ltx2_3_t2v.json"
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    assert workflow["267:330"]["inputs"]["value"] is False
