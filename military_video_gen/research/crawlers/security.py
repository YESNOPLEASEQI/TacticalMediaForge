"""SSRF-resistant public URL validation for research crawling."""

import asyncio
import inspect
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class UnsafeURLError(ValueError):
    """A URL is outside the permitted public HTTP(S) boundary."""


Resolver = Callable[[str], Iterable[str] | Awaitable[Iterable[str]]]
_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
}
_PROXY_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")


def normalize_public_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("only public HTTP(S) URLs are permitted")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURLError("authenticated URLs are not permitted")
    if not parsed.hostname:
        raise UnsafeURLError("URL host is required")
    host = parsed.hostname.lower().rstrip(".")
    port = f":{parsed.port}" if parsed.port else ""
    if ":" in host:
        host = f"[{host}]"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit(
        (parsed.scheme.lower(), f"{host}{port}", path, urlencode(sorted(query)), "")
    ).rstrip("/")


def _ensure_public_ip(address: str, *, allow_proxy_fake_ip: bool = False) -> None:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as error:
        raise UnsafeURLError(f"invalid resolved IP address: {address}") from error
    if parsed.version == 6 and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    if (
        allow_proxy_fake_ip
        and parsed.version == 4
        and parsed in _PROXY_FAKE_IP_NETWORK
    ):
        return
    if not parsed.is_global:
        raise UnsafeURLError(f"non-public IP address is not permitted: {address}")


async def _system_resolver(host: str) -> list[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({record[4][0] for record in records})


class URLSafetyChecker:
    def __init__(
        self,
        resolver: Resolver | None = None,
        *,
        allow_proxy_fake_ip: bool = False,
    ) -> None:
        self.resolver = resolver or _system_resolver
        self.allow_proxy_fake_ip = allow_proxy_fake_ip

    async def validate(self, url: str) -> str:
        normalized = normalize_public_url(url)
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
        if host.casefold() == "localhost" or host.endswith(".localhost"):
            raise UnsafeURLError("localhost is not permitted")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            result = self.resolver(host)
            addresses = list(await result) if inspect.isawaitable(result) else list(result)
        else:
            _ensure_public_ip(host)
            return normalized
        if not addresses:
            raise UnsafeURLError("host did not resolve")
        for address in addresses:
            _ensure_public_ip(
                address,
                allow_proxy_fake_ip=self.allow_proxy_fake_ip,
            )
        return normalized
