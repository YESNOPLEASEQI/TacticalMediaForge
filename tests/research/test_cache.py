from datetime import UTC, datetime, timedelta

from military_video_gen.research.cache import ResearchCache


def test_positive_failed_and_official_ttls(tmp_path) -> None:
    now = datetime(2026, 7, 22, tzinfo=UTC)
    cache = ResearchCache(tmp_path, clock=lambda: now)
    cache.put("https://example.org/a", "v1", {"body": "a"})
    cache.put("https://example.org/b", "v1", {"body": "b"}, official=True)
    cache.put_failure("https://example.org/c", "v1", "timeout")

    cache.clock = lambda: now + timedelta(hours=25)

    assert cache.get("https://example.org/a", "v1") is None
    assert cache.get("https://example.org/b", "v1") == {"body": "b"}
    assert cache.get_failure("https://example.org/c", "v1") is None


def test_force_refresh_bypasses_positive_cache(tmp_path) -> None:
    cache = ResearchCache(tmp_path)
    cache.put("https://example.org/a", "v1", {"body": "cached"})

    assert cache.get("https://example.org/a", "v1", force_refresh=True) is None
    assert cache.get("https://example.org/a", "v1") == {"body": "cached"}


def test_cache_key_includes_normalized_url_and_config_version(tmp_path) -> None:
    cache = ResearchCache(tmp_path)
    cache.put("HTTPS://Example.org/a/?utm_source=x", "v1", {"body": "one"})

    assert cache.get("https://example.org/a", "v1") == {"body": "one"}
    assert cache.get("https://example.org/a", "v2") is None
