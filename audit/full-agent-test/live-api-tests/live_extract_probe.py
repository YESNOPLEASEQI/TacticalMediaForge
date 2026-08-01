import asyncio
import json

from dotenv import load_dotenv

from api.dependencies import get_military_video_gen
from military_video_gen.config import config_manager
from military_video_gen.research.models import ResearchRequest, SearchCandidate
from military_video_gen.research.service import build_research_service


async def main() -> None:
    load_dotenv()
    core = await get_military_video_gen()
    service = build_research_service(config_manager.config.research, core.llm)
    candidate = SearchCandidate(
        url="https://www.lockheedmartin.com/en-us/news/features/history/f16.html",
        title="F-16 Fighting Falcon History | Lockheed Martin",
        snippet="Official manufacturer history page.",
        query="F-16 site:lockheedmartin.com history first flight design",
    )
    documents = await service.crawl_provider.crawl_many(
        [candidate],
        force_refresh=False,
    )
    usable = [item for item in documents if not item.error and item.markdown]
    sources = service._sources_from_documents(usable, {})
    extracted = await service.evidence_extractor.extract(usable, sources)
    cleaned = service.claim_validator.clean(extracted, sources)
    request = ResearchRequest(
        project_id="1b07c106-eaf4-4ac2-8bbe-73769330f869",
        topic="根据公开可靠资料，制作F-16战斗机基础科普。",
        narrations=[
            "F-16由美国通用动力团队在20世纪70年代设计，采用融合翼身、线传飞控和气泡座舱。"
        ],
        asset_type="image",
        mode="verified",
        script_revision=1,
    )
    relevant = service._filter_relevant_claims(
        cleaned,
        sources,
        topic=request.topic,
        narrations=request.narrations,
    )
    print(
        json.dumps(
            {
                "document_count": len(usable),
                "source_scores": [source.score for source in sources],
                "extracted": [claim.model_dump(mode="json") for claim in extracted],
                "cleaned": [claim.model_dump(mode="json") for claim in cleaned],
                "relevant_ids": [claim.id for claim in relevant],
            },
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
