import httpx
import pytest

from military_video_gen.research.providers.searxng import (
    SearchUnavailableError,
    SearXNGProvider,
)


@pytest.mark.asyncio
async def test_search_sends_json_format_and_language() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/report",
                        "title": "Report",
                        "content": "Search-only summary",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider(
            "http://searxng:8080",
            engines=["baidu", "bing"],
            client=client,
        )
        results = await provider.search("aircraft", language="en")

    assert seen[0] == {
        "q": "aircraft",
        "format": "json",
        "engines": "baidu,bing",
        "language": "en",
    }
    assert results[0].snippet == "Search-only summary"


@pytest.mark.asyncio
async def test_search_skips_malformed_results() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"title": "missing URL"},
                    {"url": "javascript:bad", "title": "bad URL"},
                    {"url": "https://example.org/ok", "title": "OK"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider("http://searxng:8080", client=client)
        results = await provider.search("test")

    assert [result.title for result in results] == ["OK"]


@pytest.mark.asyncio
async def test_search_sets_english_for_an_english_query() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider("http://searxng:8080", client=client)
        await provider.search("F-16 official manufacturer history")

    assert seen["language"] == "en"


@pytest.mark.asyncio
async def test_search_maps_transport_failure_to_explicit_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider("http://searxng:8080", client=client)
        with pytest.raises(SearchUnavailableError, match="unavailable"):
            await provider.search("test")


@pytest.mark.asyncio
async def test_search_falls_back_to_enabled_engines_when_configured_engine_is_empty() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        if params.get("engines") == "dogpile":
            return httpx.Response(
                200,
                json={"results": [], "unresponsive_engines": [["dogpile", "timeout"]]},
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.org/fallback",
                        "title": "Fallback result",
                        "content": "Result from another enabled engine",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider(
            "http://searxng:8080",
            engines=["dogpile"],
            client=client,
        )
        results = await provider.search("F-16")

    assert [params.get("engines") for params in seen] == ["dogpile", None]
    assert [result.title for result in results] == ["Fallback result"]


@pytest.mark.asyncio
async def test_search_merges_enabled_engines_when_configured_engine_partially_fails() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        if params.get("engines"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://blocked.example/report",
                            "title": "Only primary result",
                        }
                    ],
                    "unresponsive_engines": [["duckduckgo", "CAPTCHA"]],
                },
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://blocked.example/report/",
                        "title": "Duplicate result",
                    },
                    {
                        "url": "https://reachable.example/one",
                        "title": "Reachable one",
                    },
                    {
                        "url": "https://reachable.example/two",
                        "title": "Reachable two",
                    },
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider(
            "http://searxng:8080",
            engines=["duckduckgo", "dogpile"],
            client=client,
        )
        results = await provider.search("stealth aircraft")

    assert [params.get("engines") for params in seen] == [
        "duckduckgo,dogpile",
        None,
    ]
    assert [result.title for result in results] == [
        "Only primary result",
        "Reachable one",
        "Reachable two",
    ]


@pytest.mark.asyncio
async def test_search_uses_enabled_engines_when_primary_results_are_too_sparse() -> None:
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        seen.append(params)
        suffix = "primary" if params.get("engines") else "fallback"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": f"https://example.org/{suffix}",
                        "title": suffix.title(),
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = SearXNGProvider(
            "http://searxng:8080",
            engines=["dogpile"],
            client=client,
        )
        results = await provider.search("F-16")

    assert [params.get("engines") for params in seen] == ["dogpile", None]
    assert [result.title for result in results] == ["Primary", "Fallback"]
