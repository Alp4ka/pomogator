import httpx
import pytest

from pomogator.domain.sync_errors import NotionSyncError
from pomogator.infrastructure.notion.client import NotionClient


@pytest.mark.asyncio
async def test_notion_get_retries_rate_limit(monkeypatch):
    calls = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"}, request=request)
        return httpx.Response(200, json={"ok": True}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = NotionClient(
            "token",
            http=http,
            min_interval_seconds=0.01,
            max_retries=5,
        )

        async def no_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr("pomogator.infrastructure.notion.client.asyncio.sleep", no_sleep)
        payload = await client._get("/pages/x")
        assert payload == {"ok": True}
        assert calls["n"] == 3


@pytest.mark.asyncio
async def test_notion_get_raises_friendly_after_exhausted_429(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"}, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = NotionClient(
            "token",
            http=http,
            min_interval_seconds=0.01,
            max_retries=2,
        )

        async def no_sleep(_seconds: float) -> None:
            return None

        monkeypatch.setattr("pomogator.infrastructure.notion.client.asyncio.sleep", no_sleep)
        with pytest.raises(NotionSyncError) as exc:
            await client._get("/pages/x")
        assert exc.value.code == "rate_limited"
        assert "http" not in str(exc.value).casefold()
