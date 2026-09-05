"""SOCKS5 proxy pool backed by a remote host:port list."""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

DEFAULT_PROXY_LIST_URL = "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"
TELEGRAM_PROBE_URL = "https://api.telegram.org"
NOTION_PROBE_URL = "https://api.notion.com/v1/users/me"


def parse_proxy_lines(text: str) -> list[str]:
    """Parse ``host:port`` lines into ``socks5://`` URLs."""
    proxies: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "://" in line:
            parsed = urlparse(line)
            if parsed.hostname and parsed.port:
                scheme = parsed.scheme or "socks5"
                if scheme.startswith("socks"):
                    proxies.append(f"{scheme}://{parsed.hostname}:{parsed.port}")
            continue
        if ":" not in line:
            continue
        host, port_s = line.rsplit(":", 1)
        host = host.strip().strip("[]")
        if not host or not port_s.isdigit():
            continue
        proxies.append(f"socks5://{host}:{port_s}")
    return proxies


async def https_reachable(
    url: str,
    proxy_url: str | None = None,
    *,
    timeout_seconds: float = 10.0,
    headers: dict[str, str] | None = None,
) -> bool:
    """Return True when ``url`` responds with a non-HTML body through optional SOCKS5."""
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = await client.get(url, headers=headers)
            content_type = response.headers.get("content-type", "").lower()
            # Cloudflare/geo blocks often return HTML 403/503 instead of the real API.
            if "text/html" in content_type:
                return False
            return True
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        log.debug("HTTPS probe failed via %s for %s: %s", proxy_url or "direct", url, exc)
        return False


async def telegram_reachable(
    proxy_url: str | None = None, *, timeout_seconds: float = 10.0
) -> bool:
    return await https_reachable(TELEGRAM_PROBE_URL, proxy_url, timeout_seconds=timeout_seconds)


async def notion_reachable(
    token: str,
    proxy_url: str | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> bool:
    return await https_reachable(
        NOTION_PROBE_URL,
        proxy_url,
        timeout_seconds=timeout_seconds,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Accept": "application/json",
        },
    )


class SocksProxyPool:
    """Fetch a public SOCKS5 list and pick a random working entry."""

    def __init__(
        self,
        list_url: str = DEFAULT_PROXY_LIST_URL,
        *,
        cache_ttl_seconds: float = 300.0,
        probe_timeout: float = 10.0,
        max_acquire_attempts: int = 12,
    ) -> None:
        self.list_url = list_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.probe_timeout = probe_timeout
        self.max_acquire_attempts = max_acquire_attempts
        self._proxies: list[str] = []
        self._failed: set[str] = set()
        self._fetched_at: float = 0.0

    async def refresh(self) -> None:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(self.list_url)
            response.raise_for_status()
        proxies = parse_proxy_lines(response.text)
        if not proxies:
            raise RuntimeError(f"SOCKS5 list is empty: {self.list_url}")
        self._proxies = proxies
        self._fetched_at = time.monotonic()
        self._failed &= set(proxies)
        log.info("Loaded %s SOCKS5 proxies from %s", len(proxies), self.list_url)

    async def _ensure_fresh(self) -> None:
        stale = (time.monotonic() - self._fetched_at) >= self.cache_ttl_seconds
        if not self._proxies or stale:
            await self.refresh()

    def mark_failed(self, proxy_url: str) -> None:
        self._failed.add(proxy_url)
        log.info("Marked SOCKS5 proxy as failed: %s", proxy_url)

    def _candidates(self) -> list[str]:
        return [proxy for proxy in self._proxies if proxy not in self._failed]

    async def next_candidate(self) -> str:
        await self._ensure_fresh()
        candidates = self._candidates()
        if not candidates:
            self._failed.clear()
            await self.refresh()
            candidates = self._candidates()
        if not candidates:
            raise RuntimeError("No SOCKS5 proxies available")
        return random.choice(candidates)

    async def acquire(
        self,
        *,
        probe_url: str = TELEGRAM_PROBE_URL,
        headers: dict[str, str] | None = None,
    ) -> str:
        """Pick a random proxy that can reach ``probe_url``."""
        last_error = "no candidates"
        for _ in range(self.max_acquire_attempts):
            proxy = await self.next_candidate()
            if await https_reachable(
                probe_url,
                proxy,
                timeout_seconds=self.probe_timeout,
                headers=headers,
            ):
                log.info("Acquired working SOCKS5 proxy for %s: %s", probe_url, proxy)
                return proxy
            self.mark_failed(proxy)
            last_error = proxy
        raise RuntimeError(
            f"Failed to acquire working SOCKS5 proxy after {self.max_acquire_attempts} attempts "
            f"(probe={probe_url}, last={last_error})"
        )


async def resolve_socks_proxy(
    pool: SocksProxyPool,
    *,
    probe_url: str,
    headers: dict[str, str] | None = None,
    label: str,
) -> str | None:
    """Return None when direct access works, otherwise a working SOCKS5 URL."""
    if await https_reachable(
        probe_url,
        None,
        timeout_seconds=pool.probe_timeout,
        headers=headers,
    ):
        log.info("%s reachable directly; SOCKS5 not required", label)
        return None
    log.warning("%s unreachable directly; acquiring SOCKS5 proxy", label)
    return await pool.acquire(probe_url=probe_url, headers=headers)
