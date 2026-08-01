import json

import httpx
import pytest

from military_video_gen.config.schema import ResearchConfig
from military_video_gen.research.monitor import (
    ResearchMonitor,
    collect_research_diagnostics,
)


def test_monitor_persists_recent_events_and_redacts_credentials(tmp_path) -> None:
    monitor = ResearchMonitor(tmp_path / "research-monitor.jsonl")

    monitor.record(
        event="job_failed",
        status="failed",
        job_id="job-1",
        project_id="project-1",
        phase="searching",
        message=(
            "Bearer top-secret token=also-secret "
            "https://user:password@example.test/search?q=classified"
        ),
        metrics={"completed": 1, "total": 4},
    )

    raw = monitor.path.read_text(encoding="utf-8")
    assert "top-secret" not in raw
    assert "also-secret" not in raw
    assert "password" not in raw
    assert "classified" not in raw
    event = monitor.read_recent(limit=1)[0]
    assert event["event"] == "job_failed"
    assert event["job_id"] == "job-1"
    assert event["metrics"] == {"completed": 1, "total": 4}
    assert event["timestamp"].endswith("Z")


def test_monitor_rotates_bounded_jsonl_files(tmp_path) -> None:
    monitor = ResearchMonitor(
        tmp_path / "research-monitor.jsonl",
        max_bytes=220,
        backup_count=2,
    )

    for index in range(8):
        monitor.record(event="progress", status="running", message=f"event-{index}")

    assert monitor.path.exists()
    assert monitor.path.with_name("research-monitor.jsonl.1").exists()
    assert len(monitor.read_recent(limit=3)) == 3


@pytest.mark.asyncio
async def test_diagnostics_probes_each_enabled_dependency_and_reports_ready(
    tmp_path,
    monkeypatch,
) -> None:
    requested_paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": "https://example.test"}]})
        return httpx.Response(200, json={"status": "ok"})

    config = ResearchConfig(
        enabled=True,
        search={"base_url": "http://searxng.test:8080"},
        crawl={
            "base_url": "http://crawl4ai.test:11235",
            "auth_token_env": "TEST_CRAWL_TOKEN",
        },
    )
    monkeypatch.setenv("TEST_CRAWL_TOKEN", "runtime-secret")
    monitor = ResearchMonitor(tmp_path / "events.jsonl")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await collect_research_diagnostics(
            config,
            monitor=monitor,
            client=client,
        )

    assert result["status"] == "ready"
    assert result["token_configured"] is True
    assert result["services"]["searxng"]["status"] == "reachable"
    assert result["services"]["crawl4ai"]["status"] == "reachable"
    assert requested_paths == ["/search", "/health"]
    assert "runtime-secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_diagnostics_reports_one_unreachable_dependency_without_raising(
    tmp_path,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "searxng.test":
            return httpx.Response(
                200,
                json={"results": [{"url": "https://example.test"}]},
            )
        return httpx.Response(503, text="service unavailable token=secret")

    config = ResearchConfig(
        enabled=True,
        search={"base_url": "http://searxng.test:8080"},
        crawl={"base_url": "http://crawl4ai.test:11235"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await collect_research_diagnostics(
            config,
            monitor=ResearchMonitor(tmp_path / "events.jsonl"),
            client=client,
        )

    assert result["status"] == "degraded"
    assert result["services"]["searxng"]["status"] == "reachable"
    assert result["services"]["crawl4ai"]["status"] == "unreachable"
    assert "secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_diagnostics_rejects_healthy_searxng_with_no_search_results(
    tmp_path,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={"status": "ok"})

    config = ResearchConfig(
        enabled=True,
        search={"base_url": "http://searxng.test:8080"},
        crawl={"base_url": "http://crawl4ai.test:11235"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        result = await collect_research_diagnostics(
            config,
            monitor=ResearchMonitor(tmp_path / "events.jsonl"),
            client=client,
        )

    assert result["status"] == "degraded"
    assert result["services"]["searxng"] == {
        "status": "unreachable",
        "latency_ms": result["services"]["searxng"]["latency_ms"],
        "error": "search_empty",
    }
