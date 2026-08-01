import asyncio
import json
import socket
from urllib.parse import urlsplit

import httpx
import pytest

from military_video_gen.config.schema import ResearchCrawlConfig
from military_video_gen.research.crawlers.crawl4ai import (
    Crawl4AIProvider,
    CrawlResponseTooLarge,
)
from military_video_gen.research.crawlers.security import UnsafeURLError, URLSafetyChecker
from military_video_gen.research.models import SearchCandidate


def public_checker() -> URLSafetyChecker:
    return URLSafetyChecker(resolver=lambda _host: ["8.8.8.8"])


def test_crawl_provider_applies_proxy_fake_ip_configuration() -> None:
    provider = Crawl4AIProvider(ResearchCrawlConfig(allow_proxy_fake_ip=True))

    assert provider.safety_checker.allow_proxy_fake_ip is True


@pytest.mark.asyncio
async def test_crawl_uses_runtime_bearer_token_and_safe_parameters(monkeypatch) -> None:
    monkeypatch.setenv("CRAWL4AI_API_TOKEN", "secret-token")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/report",
                        "title": "Report",
                        "markdown": "verified body text",
                        "content_type": "text/html",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(
            ResearchCrawlConfig(max_redirects=5),
            client=client,
            safety_checker=public_checker(),
        )
        docs = await provider.crawl_many(
            [SearchCandidate(url="https://example.org/report", title="Report")],
            force_refresh=False,
        )

    assert seen["authorization"] == "Bearer secret-token"
    assert seen["payload"]["crawler_config"]["check_robots_txt"] is False
    assert seen["payload"]["crawler_config"]["max_redirects"] == 0
    assert "js_code" not in repr(seen["payload"])
    assert docs[0].markdown == "verified body text"
    assert "secret-token" not in repr(docs)


@pytest.mark.asyncio
async def test_crawl_uses_configured_request_timeout() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json={"results": []})

    config = ResearchCrawlConfig(
        connect_timeout_seconds=9,
        request_timeout_seconds=71,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(config, client=client, safety_checker=public_checker())
        await provider.crawl_many(
            [SearchCandidate(url="https://example.org/report", title="Report")],
            force_refresh=False,
        )

    assert seen["timeout"]["connect"] == 9
    assert seen["timeout"]["read"] == 71


@pytest.mark.asyncio
async def test_crawl_timeout_is_recorded_and_next_candidate_continues() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/crawl"):
            payload = json.loads(request.content)
            if payload["urls"] == ["https://slow.example.org/report"]:
                raise httpx.ReadTimeout("slow page", request=request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://fast.example.org/report",
                        "title": "Fast report",
                        "markdown": "usable evidence",
                    }
                ]
            },
        )

    candidates = [
        SearchCandidate(url="https://slow.example.org/report", title="Slow report"),
        SearchCandidate(url="https://fast.example.org/report", title="Fast report"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(
            ResearchCrawlConfig(), client=client, safety_checker=public_checker()
        )
        docs = await provider.crawl_many(candidates, force_refresh=False)

    assert [(doc.title, doc.error) for doc in docs] == [
        ("Slow report", "crawl_timeout"),
        ("Fast report", None),
    ]


@pytest.mark.asyncio
async def test_dns_failure_is_recorded_and_next_candidate_continues() -> None:
    def resolver(host: str) -> list[str]:
        if host == "missing.example.org":
            raise socket.gaierror(11002, "getaddrinfo failed")
        return ["8.8.8.8"]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://working.example.org/report",
                        "title": "Working report",
                        "markdown": "usable evidence",
                    }
                ]
            },
        )

    candidates = [
        SearchCandidate(url="https://missing.example.org/report", title="Missing"),
        SearchCandidate(url="https://working.example.org/report", title="Working"),
    ]
    checker = URLSafetyChecker(resolver=resolver)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        docs = await Crawl4AIProvider(
            ResearchCrawlConfig(), client=client, safety_checker=checker
        ).crawl_many(candidates, force_refresh=False)

    assert [(doc.title, doc.error) for doc in docs] == [
        ("Missing", "dns_resolution_failed"),
        ("Working report", None),
    ]


@pytest.mark.asyncio
async def test_crawl_normalizes_grouped_links_from_crawl4ai_089() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/report",
                        "markdown": {"raw_markdown": "evidence"},
                        "metadata": {"title": "Metadata title"},
                        "response_headers": {"content-type": "text/html; charset=utf-8"},
                        "links": {
                            "internal": [
                                {"href": "/details"},
                                {"href": "https://example.org/absolute"},
                            ],
                            "external": [{"href": "https://other.example.net/source"}],
                        },
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(
            ResearchCrawlConfig(), client=client, safety_checker=public_checker()
        )
        docs = await provider.crawl_many(
            [SearchCandidate(url="https://example.org/report", title="Search title")],
            force_refresh=False,
        )

    assert docs[0].title == "Metadata title"
    assert docs[0].content_type == "text/html; charset=utf-8"
    assert [str(link) for link in docs[0].links] == [
        "https://example.org/details",
        "https://example.org/absolute",
        "https://other.example.net/source",
    ]


@pytest.mark.asyncio
async def test_crawl_respects_global_and_per_domain_concurrency() -> None:
    active = 0
    max_active = 0
    per_domain: dict[str, int] = {}
    max_per_domain: dict[str, int] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, max_active
        url = json.loads(request.content)["urls"][0]
        domain = urlsplit(url).hostname or ""
        active += 1
        per_domain[domain] = per_domain.get(domain, 0) + 1
        max_active = max(max_active, active)
        max_per_domain[domain] = max(max_per_domain.get(domain, 0), per_domain[domain])
        await asyncio.sleep(0.02)
        active -= 1
        per_domain[domain] -= 1
        return httpx.Response(
            200,
            json={"results": [{"url": url, "markdown": "evidence"}]},
        )

    candidates = [
        SearchCandidate(url="https://one.example.org/a", title="One A"),
        SearchCandidate(url="https://one.example.org/b", title="One B"),
        SearchCandidate(url="https://two.example.org/a", title="Two A"),
        SearchCandidate(url="https://three.example.org/a", title="Three A"),
    ]
    config = ResearchCrawlConfig(global_concurrency=2, per_domain_concurrency=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        docs = await Crawl4AIProvider(
            config, client=client, safety_checker=public_checker()
        ).crawl_many(candidates, force_refresh=False)

    assert len(docs) == 4
    assert max_active == 2
    assert max_per_domain["one.example.org"] == 1


@pytest.mark.asyncio
async def test_crawl_revalidates_returned_final_url() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "http://169.254.169.254/latest/meta-data/",
                        "title": "Redirected",
                        "markdown": "secret",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(
            ResearchCrawlConfig(), client=client, safety_checker=public_checker()
        )
        with pytest.raises(UnsafeURLError):
            await provider.crawl_many(
                [SearchCandidate(url="https://example.org/report", title="Report")],
                force_refresh=False,
            )


@pytest.mark.asyncio
async def test_crawl_rejects_oversized_streamed_response() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048)

    config = ResearchCrawlConfig(max_html_bytes=1024, max_pdf_bytes=1024)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(config, client=client, safety_checker=public_checker())
        with pytest.raises(CrawlResponseTooLarge):
            await provider.crawl_many(
                [SearchCandidate(url="https://example.org/report", title="Report")],
                force_refresh=False,
            )


@pytest.mark.asyncio
async def test_pdf_without_text_layer_is_recorded_as_failed_document() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/report.pdf",
                        "title": "Scanned PDF",
                        "markdown": "",
                        "content_type": "application/pdf",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = Crawl4AIProvider(
            ResearchCrawlConfig(), client=client, safety_checker=public_checker()
        )
        docs = await provider.crawl_many(
            [SearchCandidate(url="https://example.org/report.pdf", title="PDF")],
            force_refresh=False,
        )

    assert docs[0].error == "pdf_without_text_layer"
