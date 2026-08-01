import pytest

from military_video_gen.research.query_planner import QueryPlanner


class FailingLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, **_kwargs):
        self.calls += 1
        raise ConnectionError("provider unavailable")


@pytest.mark.asyncio
async def test_query_planner_uses_narration_to_disambiguate_without_calling_llm() -> None:
    llm = FailingLLM()

    first = await QueryPlanner(llm).plan("F-16", ["first narration"])
    second = await QueryPlanner(llm).plan("F-16", ["different narration"])

    assert first != second
    assert len(first) == 5
    assert len(set(first)) == 5
    assert all(query.startswith("F-16 ") for query in first)
    assert any("first" in query for query in first)
    assert any("different" in query for query in second)
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_query_planner_disambiguates_cannon_from_same_name_person() -> None:
    queries = await QueryPlanner(FailingLLM()).plan(
        "大炮",
        [
            "炮管承受火药爆燃的冲击，并为弹丸提供前进路径。",
            "火药推动弹丸穿过炮管，膛线让弹丸保持稳定。",
        ],
    )

    combined = " ".join(queries)
    assert len(queries) == 5
    assert "炮管" in combined
    assert "弹丸" in combined
    assert "军事装备" in combined


@pytest.mark.asyncio
async def test_query_planner_keeps_non_latin_topic_in_every_query() -> None:
    llm = FailingLLM()

    queries = await QueryPlanner(llm).plan(
        "高超音速滑翔飞行器",
        ["乘波体依靠激波产生升力"],
    )

    assert len(queries) == 5
    assert all("高超音速滑翔飞行器" in query for query in queries)
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_query_planner_adds_concise_cross_language_equipment_query() -> None:
    queries = await QueryPlanner(FailingLLM()).plan(
        "根据公开资料介绍F-16战斗机的首飞与外观",
        ["F-16由美国研制，并在1970年代完成首飞。"],
    )

    assert queries[0] == "F-16 fighter aircraft first flight manufacturer history"
    assert queries[1] == "F-16 fighter aircraft official manufacturer design"
