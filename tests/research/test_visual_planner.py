import json
import re
import asyncio

from military_video_gen.research.models import EvidenceClaim, EvidenceQuote, VisualFact
from military_video_gen.research.visual_fact_extractor import VisualFactExtractor
from military_video_gen.research.visual_planner import VisualPlanner


class FakeLLM:
    async def generate_structured(self, *, response_type, **_kwargs):
        return response_type.model_validate(
            {
                "visual_facts": [
                    {
                        "id": "visual-good",
                        "fact": "swept wing",
                        "claim_ids": ["claim-good"],
                        "allowed_detail": "swept wing",
                        "confidence": 0.85,
                    },
                    {
                        "id": "visual-low",
                        "fact": "tail",
                        "claim_ids": ["claim-good"],
                        "allowed_detail": "tail",
                        "confidence": 0.7,
                    },
                    {
                        "id": "visual-bad-ref",
                        "fact": "missile",
                        "claim_ids": ["claim-unverified"],
                        "allowed_detail": "missile",
                        "confidence": 0.95,
                    },
                ]
            }
        )


def claim(
    claim_id: str,
    status: str,
    *,
    confidence: float = 0.9,
) -> EvidenceClaim:
    return EvidenceClaim(
        id=claim_id,
        statement="statement",
        subject="subject",
        predicate="predicate",
        value="value",
        source_ids=["source-1"],
        evidence_quotes=[EvidenceQuote(source_id="source-1", quote="quote")],
        status=status,
        confidence=confidence,
    )


async def test_visual_facts_enforce_threshold_and_reject_unsupported_references() -> None:
    facts = await VisualFactExtractor(FakeLLM(), minimum_confidence=0.8).extract(
        [claim("claim-good", "verified"), claim("claim-unverified", "unsupported")]
    )

    assert facts == [
        VisualFact(
            id="visual-good",
            fact="swept wing",
            claim_ids=["claim-good"],
            allowed_detail="swept wing",
            confidence=0.85,
        ),
    ]


async def test_visual_fact_accepts_low_confidence_claim_and_caps_confidence() -> None:
    class LowConfidenceLLM:
        async def generate_structured(self, *, response_type, **_kwargs):
            return response_type.model_validate(
                {
                    "visual_facts": [
                        {
                            "id": "visual-low-confidence",
                            "fact": "swept wing",
                            "claim_ids": ["claim-low-confidence"],
                            "allowed_detail": "swept wing",
                            "confidence": 0.9,
                        }
                    ]
                }
            )

    facts = await VisualFactExtractor(
        LowConfidenceLLM(),
        minimum_confidence=0.65,
    ).extract(
        [
            claim(
                "claim-low-confidence",
                "low_confidence_verified",
                confidence=0.67,
            )
        ]
    )

    assert len(facts) == 1
    assert facts[0].confidence == 0.67


async def test_visual_planner_generates_distinct_scenes_independently() -> None:
    class DistinctLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def __call__(self, **_kwargs):
            self.calls += 1
            prompt = (
                "carrier deck tracking shot " + "observation " * 36
                if '"narration": "First narration"' in _kwargs["prompt"]
                else "hangar inspection close-up " + "observation " * 37
            )
            return json.dumps({"video_prompts": [prompt]})

    llm = DistinctLLM()
    _, scenes = await VisualPlanner(llm).plan(
        ["First narration", "Second narration"], [], [], "video"
    )

    assert llm.calls == 2
    assert scenes[0].media_prompt != scenes[1].media_prompt
    assert all(scene.generic_fallback is None for scene in scenes)


async def test_video_scene_timeout_uses_the_configured_planning_budget() -> None:
    class DelayedLLM:
        async def __call__(self, **_kwargs):
            await asyncio.sleep(0.02)
            return json.dumps({
                "video_prompts": [
                    "F-16 documentary tracking shot " + "observation " * 36
                ]
            })

    _, scenes = await VisualPlanner(
        DelayedLLM(),
        scene_timeout_seconds=0.1,
    ).plan(["F-16 overview"], [], [], "video")

    assert scenes[0].warnings == []


def test_fallback_prompts_remain_unique_beyond_five_scenes() -> None:
    _, scenes = VisualPlanner.fallback_plan(
        [f"F-16 narration {index}" for index in range(1, 8)],
        "video",
        topic="F-16",
    )

    prompts = [scene.media_prompt for scene in scenes]
    assert len(prompts) == 7
    assert len(set(prompts)) == 7


async def test_visual_planner_estimates_scene_duration_from_narration() -> None:
    class PromptLLM:
        async def __call__(self, **_kwargs):
            return json.dumps({"video_prompts": ["documentary tracking shot"]})

    narration = "1234567890"
    _, scenes = await VisualPlanner(PromptLLM()).plan(
        [narration], [], [], "video"
    )

    assert scenes[0].estimated_duration == 3


def research_claim(
    claim_id: str,
    statement: str,
    *,
    status: str = "partially_supported",
) -> EvidenceClaim:
    return EvidenceClaim(
        id=claim_id,
        statement=statement,
        subject="subject",
        predicate="has",
        value=statement,
        source_ids=["source-1"],
        evidence_quotes=[EvidenceQuote(source_id="source-1", quote=statement)],
        status=status,
        confidence=0.8,
    )


def test_each_narration_gets_only_its_most_relevant_reference_notes() -> None:
    planner = VisualPlanner(FakeLLM())
    contexts = planner.select_research_contexts(
        ["雷达天线在机场进行旋转扫描", "航母甲板上舰载机准备起飞"],
        [],
        [
            research_claim("radar", "机场雷达天线可以持续旋转扫描"),
            research_claim("carrier", "航母飞行甲板用于舰载机起飞"),
            research_claim("unrelated", "潜艇在深海保持静默航行"),
        ],
    )

    assert contexts[0] == ["机场雷达天线可以持续旋转扫描"]
    assert contexts[1] == ["航母飞行甲板用于舰载机起飞"]


def test_unmatched_narration_gets_no_unrelated_general_claims() -> None:
    planner = VisualPlanner(FakeLLM())
    contexts = planner.select_research_contexts(
        ["完全无关的场景关键词"],
        [],
        [
            research_claim("best", "General safe reference one"),
            research_claim("second", "General safe reference two"),
            research_claim("third", "General safe reference three"),
            research_claim("conflict", "Unsafe general reference", status="conflicted"),
        ],
    )

    assert contexts == [[]]
    assert "Unsafe general reference" not in contexts[0]


async def test_conflicting_precise_claim_is_not_added_to_generation_prompt() -> None:
    class CapturingLLM:
        def __init__(self) -> None:
            self.prompt = ""

        async def __call__(self, **kwargs):
            self.prompt = kwargs["prompt"]
            return json.dumps({"video_prompts": ["A distinct documentary tracking shot"]})

    llm = CapturingLLM()
    await VisualPlanner(llm).plan(
        ["导弹高速飞行"],
        [],
        [],
        "video",
        [research_claim("conflict", "Maximum speed is Mach 12", status="conflicted")],
    )

    assert "Mach 12" not in llm.prompt


async def test_relevant_web_reference_is_added_to_its_scene_prompt() -> None:
    class CapturingLLM:
        def __init__(self) -> None:
            self.prompt = ""

        async def __call__(self, **kwargs):
            self.prompt = kwargs["prompt"]
            return json.dumps({"video_prompts": ["Radar rotates as the camera tracks it"]})

    llm = CapturingLLM()
    await VisualPlanner(llm).plan(
        ["机场雷达天线旋转扫描"],
        [],
        [],
        "video",
        [research_claim("radar", "机场雷达天线可以持续旋转扫描")],
    )

    assert "机场雷达天线可以持续旋转扫描" in llm.prompt


def test_fallback_prompts_are_english_only_even_for_chinese_narration() -> None:
    _, scenes = VisualPlanner.fallback_plan(
        ["雷达天线旋转扫描", "操作员观察显示器"],
        "video",
        topic="雷达",
    )

    assert len(scenes) == 2
    assert scenes[0].media_prompt != scenes[1].media_prompt
    assert all(
        not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", scene.media_prompt)
        for scene in scenes
    )


def test_cannon_fallback_keeps_a_concrete_subject_in_every_scene() -> None:
    _, scenes = VisualPlanner.fallback_plan(
        ["炮管承受冲击", "火药推动弹丸", "膛线稳定弹丸"],
        "video",
        topic="大炮",
    )

    assert all("artillery cannon" in scene.media_prompt for scene in scenes)
    assert all("soundscape" in scene.media_prompt for scene in scenes)
    assert all("credible military technology subject" not in scene.media_prompt for scene in scenes)


async def test_cross_language_narration_uses_entailment_mapping() -> None:
    class MappingLLM:
        async def __call__(self, **kwargs):
            if "# Cross-language evidence mapping" in kwargs["prompt"]:
                return json.dumps({
                    "mappings": [
                        {"scene_index": 1, "claim_ids": ["claim-design"]},
                    ]
                })
            return json.dumps({
                "video_prompts": [
                    "A restrained documentary view of an F-16 in a neutral hangar"
                ]
            })

    _, scenes = await VisualPlanner(MappingLLM()).plan(
        ["F-16由通用动力团队设计"],
        [],
        [],
        "video",
        [
            research_claim(
                "claim-design",
                "The F-16 was designed by a General Dynamics team.",
            )
        ],
    )

    assert scenes[0].claim_ids == ["claim-design"]


async def test_cross_language_mapping_retries_an_empty_model_response() -> None:
    class EmptyThenValidLLM:
        def __init__(self) -> None:
            self.mapping_calls = 0

        async def __call__(self, **kwargs):
            if "# Cross-language evidence mapping" in kwargs["prompt"]:
                self.mapping_calls += 1
                if self.mapping_calls == 1:
                    return ""
                return json.dumps({
                    "mappings": [
                        {"scene_index": 1, "claim_ids": ["claim-design"]},
                    ]
                })
            return json.dumps({
                "video_prompts": ["An F-16 documentary observation shot"]
            })

    llm = EmptyThenValidLLM()
    _, scenes = await VisualPlanner(llm).plan(
        ["F-16由通用动力团队设计"],
        [],
        [],
        "video",
        [
            research_claim(
                "claim-design",
                "The F-16 was designed by a General Dynamics team.",
            )
        ],
    )

    assert llm.mapping_calls == 2
    assert scenes[0].claim_ids == ["claim-design"]
