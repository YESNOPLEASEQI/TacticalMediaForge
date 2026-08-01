import asyncio
import json

import pytest

from military_video_gen.prompts.topic_narration import (
    build_topic_narration_prompt,
    build_topic_narrative_plan_prompt,
)
from military_video_gen.utils.content_generators import (
    ScriptGenerationTimeoutError,
    generate_narrations_from_topic,
)


def narrative_plan(scene_count: int) -> dict:
    return {
        "central_question": "可变后掠翼解决了什么矛盾",
        "narrative_angle": "从航母起降到高速飞行",
        "opening_intent": "从两种飞行状态的冲突切入",
        "beats": [
            {
                "purpose": f"推进第{index + 1}部分",
                "key_point": f"关键点{index + 1}",
                "bridge": f"连接到第{index + 2}部分",
            }
            for index in range(scene_count)
        ],
        "ending_intent": "回到机翼如何协调两种状态",
    }


class TwoStageLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, *, prompt, **_kwargs):
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return json.dumps(narrative_plan(3), ensure_ascii=False)
        return json.dumps(
            {
                "narrations": [
                    "航母起降和高速截击，对机翼提出了相反要求",
                    "F-14让机翼随速度改变角度，把两种状态连接起来",
                    "这套变化最终让同一架飞机兼顾低速升力与高速性能",
                ]
            },
            ensure_ascii=False,
        )


@pytest.mark.asyncio
async def test_topic_narration_uses_plan_before_writing() -> None:
    llm = TwoStageLLM()

    narrations = await generate_narrations_from_topic(
        llm_service=llm,
        topic="F-14可变后掠翼",
        n_scenes=3,
        min_words=8,
        max_words=30,
        reference_context="机翼会随飞行状态改变后掠角",
    )

    assert len(llm.prompts) == 2
    assert "Do not write the finished narration" in llm.prompts[0]
    assert "从航母起降到高速飞行" in llm.prompts[1]
    assert "not independent fact cards" in llm.prompts[1]
    assert narrations[0].startswith("航母起降")


@pytest.mark.asyncio
async def test_invalid_plan_falls_back_without_blocking_script_generation() -> None:
    class InvalidPlanLLM:
        def __init__(self) -> None:
            self.calls = 0
            self.writing_prompt = ""

        async def __call__(self, *, prompt, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return '{"beats": []}'
            self.writing_prompt = prompt
            return '{"narrations": ["第一段自然旁白", "第二段自然收束"]}'

    llm = InvalidPlanLLM()
    result = await generate_narrations_from_topic(
        llm_service=llm,
        topic="雷达工作原理",
        n_scenes=2,
    )

    assert result == ["第一段自然旁白", "第二段自然收束"]
    assert "轻量" not in llm.writing_prompt
    assert "回应开头" in llm.writing_prompt


def test_prompts_define_dynamic_story_thread_and_short_subtitle_rhythm() -> None:
    plan_prompt = build_topic_narrative_plan_prompt("隐身技术", 5)
    writing_prompt = build_topic_narration_prompt(
        "隐身技术",
        5,
        5,
        20,
        narrative_plan=json.dumps(narrative_plan(5), ensure_ascii=False),
    )

    assert "Choose the most useful narrative logic" in plan_prompt
    assert "exactly 5 beats" in plan_prompt
    assert "12 to 22 Chinese characters" in writing_prompt
    assert "one short subtitle card" in writing_prompt
    assert "At most one comma" in writing_prompt
    assert "Never chain facts with multiple commas" in writing_prompt
    assert "complete the explanation established by the opening" in writing_prompt
    assert "technical background →" not in writing_prompt
    assert "real-world limitations" not in writing_prompt


@pytest.mark.asyncio
async def test_planning_timeout_uses_fallback_then_writes_script() -> None:
    class SlowPlannerLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, *, prompt, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                await asyncio.sleep(0.02)
            return '{"narrations": ["第一段", "第二段"]}'

    llm = SlowPlannerLLM()
    result = await generate_narrations_from_topic(
        llm_service=llm,
        topic="雷达工作原理",
        n_scenes=2,
        planning_timeout_seconds=0.001,
        writing_timeout_seconds=1,
    )

    assert result == ["第一段", "第二段"]
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_writing_timeout_has_stable_error_code_without_full_retry() -> None:
    class SlowWriterLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, *, prompt, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return json.dumps(narrative_plan(2), ensure_ascii=False)
            await asyncio.sleep(0.02)

    llm = SlowWriterLLM()
    with pytest.raises(ScriptGenerationTimeoutError, match="script_generation_timeout"):
        await generate_narrations_from_topic(
            llm_service=llm,
            topic="雷达工作原理",
            n_scenes=2,
            planning_timeout_seconds=1,
            writing_timeout_seconds=0.001,
        )

    assert llm.calls == 2
