"""Deterministic query planning for a bounded research run."""

import re
from collections import Counter

from military_video_gen.services.llm_service import LLMService

_CHINESE_STOP_BIGRAMS = {
    "一个",
    "一种",
    "这个",
    "这些",
    "它们",
    "它的",
    "什么",
    "就是",
    "可以",
    "通过",
    "以及",
    "进行",
    "开始",
    "最终",
    "后来",
    "人们",
    "一样",
    "始终",
    "同一",
    "方向",
    "提供",
    "保持",
    "只能",
    "时候",
    "已经",
    "不是",
    "没有",
    "这种",
    "秘密",
    "毁灭",
    "核心",
    "究竟",
}
_EDGE_PARTICLES = set("的了是在和与为把被从到向上中里后时又也而将让但还都只")


class QueryPlanner:
    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    async def plan(self, topic: str, narrations: list[str]) -> list[str]:
        # Search must not depend on a preliminary LLM call. The narration-derived
        # terms disambiguate short or overloaded titles such as “大炮”, which may
        # otherwise resolve to a person, work, or product with the same name.
        keywords = self.narration_keywords(narrations, topic=topic)
        primary = " ".join(keywords[:4])
        secondary = " ".join(keywords[4:8] or keywords[:4])
        combined = " ".join(keywords[:8])
        identifiers = re.findall(
            r"(?<![a-z0-9])[a-z]{1,8}\s*-?\s*\d[a-z0-9-]*(?![a-z0-9])",
            topic.casefold(),
        )
        concise_queries: list[str] = []
        if identifiers:
            identifier = re.sub(r"\s+", "", identifiers[0]).upper()
            category = (
                "fighter aircraft"
                if "战斗机" in topic or "fighter" in topic.casefold()
                else "military equipment"
            )
            concise_queries = [
                f"{identifier} {category} first flight manufacturer history",
                f"{identifier} {category} official manufacturer design",
            ]
        planned_queries = [
            *concise_queries,
            f"{topic} {primary} 军事装备 工作原理",
            f"{topic} {secondary} 官方 技术资料",
            f"{topic} {combined} 结构 原理",
            f"{topic} {primary} 历史 发展",
            f"{topic} {combined} 研究 报告",
        ]
        queries: list[str] = []
        seen: set[str] = set()
        for query in planned_queries:
            cleaned = " ".join(query.split())
            if cleaned and cleaned.casefold() not in seen:
                queries.append(cleaned)
                seen.add(cleaned.casefold())
        if len(queries) < 4:
            raise ValueError("query plan must contain at least 4 distinct queries")
        return queries[:5]

    @staticmethod
    def narration_keywords(
        narrations: list[str],
        *,
        topic: str,
        limit: int = 8,
    ) -> list[str]:
        """Extract a few repeated, topic-specific terms without a tokenizer service."""
        body = " ".join(narrations).casefold()
        topic_tokens = {
            topic.casefold().strip(),
            *re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", topic.casefold()),
        }
        candidates: Counter[str] = Counter(
            re.findall(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", body)
        )
        for run in re.findall(r"[\u4e00-\u9fff]+", body):
            for size in (2, 3, 4):
                for index in range(max(0, len(run) - size + 1)):
                    value = run[index : index + size]
                    if (
                        value in _CHINESE_STOP_BIGRAMS
                        or value[0] in _EDGE_PARTICLES
                        or value[-1] in _EDGE_PARTICLES
                    ):
                        continue
                    candidates[value] += 1

        ranked = sorted(
            (
                (count * 100 + len(value), value)
                for value, count in candidates.items()
                if value not in topic_tokens and (count > 1 or not re.search(r"[\u4e00-\u9fff]", value))
            ),
            reverse=True,
        )
        selected: list[str] = []
        for _, value in ranked:
            # Prefer the most informative form instead of returning overlapping
            # variants such as “炮管”, “炮管内”, and “在炮管内”.
            if any(value in existing or existing in value for existing in selected):
                continue
            selected.append(value)
            if len(selected) >= limit:
                break
        return selected
