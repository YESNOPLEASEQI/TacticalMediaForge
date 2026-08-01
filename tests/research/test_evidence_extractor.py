from datetime import UTC, datetime

import pytest

from military_video_gen.research.evidence_extractor import EvidenceExtractor
from military_video_gen.research.models import CrawledDocument, Source


class FakeLLM:
    def __init__(self, claims: list[dict]) -> None:
        self.claims = claims
        self.user_content = ""
        self.user_contents = []
        self.system_contents = []
        self.max_tokens = None

    async def generate_structured(self, *, messages, response_type, **kwargs):
        self.user_content = messages[-1]["content"]
        self.user_contents.append(self.user_content)
        self.system_contents.append(messages[0]["content"])
        self.max_tokens = kwargs.get("max_tokens")
        return response_type.model_validate({"claims": self.claims})


def source_and_document() -> tuple[Source, CrawledDocument]:
    now = datetime.now(UTC)
    source = Source(
        id="source-1",
        url="https://example.org/report",
        title="Report",
        fetched_at=now,
        content_hash="hash",
        score=0.9,
    )
    document = CrawledDocument(
        url=source.url,
        title="Report",
        markdown="The aircraft has a swept wing and a single vertical tail.",
        content_hash="hash",
        fetched_at=now,
    )
    return source, document


@pytest.mark.asyncio
async def test_evidence_extractor_accepts_only_verbatim_body_quotes() -> None:
    source, document = source_and_document()
    llm = FakeLLM(
        [
            {
                "id": "claim-1",
                "statement": "The aircraft has a swept wing.",
                "subject": "aircraft",
                "predicate": "has",
                "value": "swept wing",
                "source_ids": ["source-1"],
                "evidence_quotes": [{"source_id": "source-1", "quote": "has a swept wing"}],
                "status": "partially_supported",
                "confidence": 0.7,
            }
        ]
    )

    claims = await EvidenceExtractor(llm).extract([document], [source])

    assert [claim.id for claim in claims] == ["claim-1"]
    assert "Search-only summary" not in llm.user_content
    assert document.markdown in llm.user_content
    assert llm.max_tokens == 4000
    assert "mechanisms" in llm.system_contents[0]
    assert "prioritizing aircraft origin" not in llm.system_contents[0]


@pytest.mark.asyncio
async def test_evidence_extractor_drops_non_verbatim_quote() -> None:
    source, document = source_and_document()
    llm = FakeLLM(
        [
            {
                "id": "claim-1",
                "statement": "Unsupported paraphrase",
                "subject": "aircraft",
                "predicate": "has",
                "value": "two tails",
                "source_ids": ["source-1"],
                "evidence_quotes": [{"source_id": "source-1", "quote": "two vertical tails"}],
                "status": "partially_supported",
                "confidence": 0.9,
            }
        ]
    )

    claims = await EvidenceExtractor(llm).extract([document], [source])

    assert claims == []


@pytest.mark.asyncio
async def test_evidence_extractor_bounds_each_body_and_total_prompt() -> None:
    now = datetime.now(UTC)
    sources = []
    documents = []
    for index in range(8):
        source = Source(
            id=f"source-{index}",
            url=f"https://example.org/report-{index}",
            title=f"Report {index}",
            fetched_at=now,
            content_hash=f"hash-{index}",
            score=0.9,
        )
        sources.append(source)
        documents.append(
            CrawledDocument(
                url=source.url,
                title=source.title,
                markdown=(
                    (f"Report {index} contains verified aircraft facts.\n" * 600) + f"TAIL-{index}"
                ),
                content_hash=source.content_hash,
                fetched_at=now,
            )
        )
    llm = FakeLLM([])

    await EvidenceExtractor(llm).extract(documents, sources)

    assert len(llm.user_contents) == 16
    assert all(len(content) < 16_000 for content in llm.user_contents)
    assert "TAIL-0" not in "".join(llm.user_contents)
    assert "source-0" in "".join(llm.user_contents)
    assert "source-7" in "".join(llm.user_contents)


@pytest.mark.asyncio
async def test_evidence_extractor_retries_an_empty_structured_response() -> None:
    source, document = source_and_document()

    class EmptyThenClaimsLLM:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_structured(self, *, response_type, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return response_type.model_validate({"claims": []})
            return response_type.model_validate(
                {
                    "claims": [
                        {
                            "id": "temporary",
                            "statement": "The aircraft has a swept wing.",
                            "subject": "aircraft",
                            "predicate": "has",
                            "value": "swept wing",
                            "source_ids": ["source-1"],
                            "evidence_quotes": [
                                {"source_id": "source-1", "quote": "has a swept wing"}
                            ],
                            "status": "partially_supported",
                            "confidence": 0.8,
                        }
                    ]
                }
            )

    llm = EmptyThenClaimsLLM()
    claims = await EvidenceExtractor(llm).extract([document], [source])

    assert llm.calls == 2
    assert [claim.id for claim in claims] == ["claim-1"]


@pytest.mark.asyncio
async def test_evidence_extractor_keeps_successful_batches_when_one_fails() -> None:
    now = datetime.now(UTC)
    sources = []
    documents = []
    for index in range(3):
        source = Source(
            id=f"source-{index}",
            url=f"https://example.org/report-{index}",
            title=f"Report {index}",
            fetched_at=now,
            content_hash=f"hash-{index}",
            score=0.9,
        )
        sources.append(source)
        documents.append(
            CrawledDocument(
                url=source.url,
                title=source.title,
                markdown=f"Body {index} contains an explicit fact.",
                content_hash=source.content_hash,
                fetched_at=now,
            )
        )

    class PartlyFailingLLM:
        async def generate_structured(self, *, messages, response_type, **_kwargs):
            content = messages[-1]["content"]
            if "source-2" in content:
                raise RuntimeError("one extraction batch failed")
            return response_type.model_validate(
                {
                    "claims": [
                        {
                            "id": "temporary-id",
                            "statement": "An explicit fact is present.",
                            "subject": "subject",
                            "predicate": "contains",
                            "value": "fact",
                            "source_ids": ["source-0"],
                            "evidence_quotes": [
                                {
                                    "source_id": "source-0",
                                    "quote": "contains an explicit fact",
                                }
                            ],
                            "status": "partially_supported",
                            "confidence": 0.8,
                        }
                    ]
                }
            )

    claims = await EvidenceExtractor(PartlyFailingLLM()).extract(documents, sources)

    assert [claim.id for claim in claims] == ["claim-1"]


@pytest.mark.asyncio
async def test_evidence_extractor_surfaces_error_when_all_batches_fail() -> None:
    now = datetime.now(UTC)
    source = Source(
        id="source-0",
        url="https://example.org/report",
        title="Report",
        fetched_at=now,
        content_hash="hash",
        score=0.9,
    )
    document = CrawledDocument(
        url=source.url,
        title=source.title,
        markdown="Body contains an explicit fact.",
        content_hash=source.content_hash,
        fetched_at=now,
    )

    class FailingLLM:
        async def generate_structured(self, **_kwargs):
            raise RuntimeError("provider response could not be parsed")

    with pytest.raises(RuntimeError, match="provider response could not be parsed"):
        await EvidenceExtractor(FailingLLM()).extract([document], [source])


def test_evidence_excerpt_prefers_relevant_body_after_navigation_prefix() -> None:
    navigation = "\n".join(
        f"[F-16 menu {index}](https://example.org/navigation/{index})" for index in range(300)
    )
    markdown = (
        navigation
        + "\nStep-by-step instructions to attack a real airbase with missiles."
        + "\n## F-16 Fighting Falcon history"
        + "\nThe F-16 has a blended-wing body and a bubble canopy."
    )

    excerpt = EvidenceExtractor._build_safe_excerpt(
        markdown,
        title="F-16 Fighting Falcon",
    )

    assert "blended-wing body and a bubble canopy" in excerpt
    assert "instructions to attack a real airbase" not in excerpt
    assert len(excerpt) <= EvidenceExtractor.MAX_BODY_CHARS
