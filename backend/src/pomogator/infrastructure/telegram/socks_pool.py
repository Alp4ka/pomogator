"""SOCKS5 proxy pool backed by a remote host:port list."""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import urlparse

import aiohttp
import httpx
from aiohttp_socks import ProxyConnector

log = logging.getLogger(__name__)

DEFAULT_PROXY_LIST_URL = "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"


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


async def telegram_reachable(
    proxy_url: str | None = None, *, timeout_seconds: float = 10.0
) -> bool:
    """Return True when ``api.telegram.org`` responds through optional SOCKS5."""
    connector: aiohttp.BaseConnector | None = None
    try:
        if proxy_url:
            connector = ProxyConnector.from_url(proxy_url)
        timeout_cfg = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout_cfg) as session:
            async with session.get("https://api.telegram.org") as response:
                return response.status < 500
    except Exception as exc:  # noqa: BLE001 — probe must never raise
        log.debug("Telegram probe failed via %s: %s", proxy_url or "direct", exc)
        return False
    finally:
        if connector is not None and not connector.closed:
            await connector.close()


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
        # Drop failure marks for proxies that disappeared from the fresh list.
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

    async def acquire(self) -> str:
        """Pick a random proxy that can reach Telegram."""
        last_error = "no candidates"
        for _ in range(self.max_acquire_attempts):
            proxy = await self.next_candidate()
            if await telegram_reachable(proxy, timeout_seconds=self.probe_timeout):
                log.info("Acquired working SOCKS5 proxy: %s", proxy)
                return proxy
            self.mark_failed(proxy)
            last_error = proxy
        raise RuntimeError(
            f"Failed to acquire working SOCKS5 proxy after {self.max_acquire_attempts} attempts "
            f"(last={last_error})"
        )
