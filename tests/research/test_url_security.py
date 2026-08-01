import pytest

from military_video_gen.research.crawlers.security import (
    UnsafeURLError,
    URLSafetyChecker,
    normalize_public_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:pass@example.com/",
        "http://localhost/test",
        "http://127.0.0.1/test",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://[::ffff:127.0.0.1]/",
    ],
)
@pytest.mark.asyncio
async def test_rejects_non_public_or_authenticated_urls(url: str) -> None:
    checker = URLSafetyChecker(resolver=lambda _host: ["8.8.8.8"])

    with pytest.raises(UnsafeURLError):
        await checker.validate(url)


@pytest.mark.asyncio
async def test_rejects_when_any_resolved_address_is_private() -> None:
    checker = URLSafetyChecker(resolver=lambda _host: ["8.8.8.8", "10.0.0.2"])

    with pytest.raises(UnsafeURLError):
        await checker.validate("https://example.com/public")


@pytest.mark.asyncio
async def test_proxy_fake_ip_requires_explicit_opt_in() -> None:
    checker = URLSafetyChecker(resolver=lambda _host: ["198.18.0.37"])

    with pytest.raises(UnsafeURLError):
        await checker.validate("https://example.com/public")


@pytest.mark.asyncio
async def test_proxy_fake_ip_is_allowed_only_for_resolved_domain() -> None:
    checker = URLSafetyChecker(
        resolver=lambda _host: ["198.18.0.37"],
        allow_proxy_fake_ip=True,
    )

    assert await checker.validate("https://example.com/public") == (
        "https://example.com/public"
    )
    with pytest.raises(UnsafeURLError):
        await checker.validate("http://198.18.0.37/public")


@pytest.mark.asyncio
async def test_dns_is_revalidated_to_detect_rebinding() -> None:
    answers = iter([["8.8.8.8"], ["192.168.1.20"]])
    checker = URLSafetyChecker(resolver=lambda _host: next(answers))

    await checker.validate("https://example.com/page")
    with pytest.raises(UnsafeURLError):
        await checker.validate("https://example.com/page")


def test_url_normalization_removes_tracking_and_fragment() -> None:
    assert normalize_public_url(
        "HTTPS://Example.COM/path/?utm_source=x&b=2&a=1#section"
    ) == "https://example.com/path?a=1&b=2"
