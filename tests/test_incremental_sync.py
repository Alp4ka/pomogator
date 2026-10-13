from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pomogator.application.sync import build_page_snapshots
from pomogator.infrastructure.notion.client import NotionClient, PageSnapshot

ROOT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CHILD = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
DATABASE = "cccccccccccccccccccccccccccccccc"
EDITED = "2026-01-01T00:00:00.000Z"


def _page_json(page_id: str, title: str, edited: str = EDITED) -> dict:
    return {
        "id": page_id,
        "last_edited_time": edited,
        "icon": {"type": "emoji", "emoji": "🇧🇷"},
        "properties": {
            "title": {"type": "title", "title": [{"plain_text": title, "annotations": {}}]}
        },
    }


def _blocks(*blocks: dict) -> dict:
    return {"results": list(blocks), "has_more": False}


@pytest.mark.asyncio
async def test_import_reuses_blocks_when_last_edited_matches(monkeypatch):
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith(f"/pages/{ROOT}"):
            return httpx.Response(200, json=_page_json(ROOT, "Brazil"), request=request)
        raise AssertionError(f"unexpected {request.url.path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = NotionClient("token", http=http, min_interval_seconds=0.01)
        monkeypatch.setattr("pomogator.infrastructure.notion.client.asyncio.sleep", _no_sleep)
        imported = await client.import_country(
            ROOT,
            "brazil",
            "🌍",
            snapshots={
                ROOT: PageSnapshot(
                    last_edited_at=EDITED,
                    document=[{"type": "paragraph", "rich_text": [{"text": "cached"}]}],
                )
            },
        )
    assert imported.root.reused is True
    assert imported.root.document[0]["rich_text"][0]["text"] == "cached"
    assert imported.flag == "🇧🇷"
    assert all("/blocks/" not in path for path in calls)
    assert calls == [f"GET /v1/pages/{ROOT}"]


@pytest.mark.asyncio
async def test_import_refetches_when_last_edited_changes(monkeypatch):
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith(f"/pages/{ROOT}"):
            return httpx.Response(
                200, json=_page_json(ROOT, "Brazil", "2026-02-02T00:00:00.000Z"), request=request
            )
        if "/blocks/" in request.url.path:
            return httpx.Response(
                200,
                json=_blocks(
                    {
                        "id": "block-1",
                        "type": "paragraph",
                        "has_children": False,
                        "paragraph": {
                            "rich_text": [{"plain_text": "fresh", "annotations": {}}],
                        },
                    }
                ),
                request=request,
            )
        raise AssertionError(f"unexpected {request.url.path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = NotionClient("token", http=http, min_interval_seconds=0.01)
        monkeypatch.setattr("pomogator.infrastructure.notion.client.asyncio.sleep", _no_sleep)
        imported = await client.import_country(
            ROOT,
            "brazil",
            "🌍",
            snapshots={
                ROOT: PageSnapshot(
                    last_edited_at=EDITED,
                    document=[{"type": "paragraph", "rich_text": [{"text": "cached"}]}],
                )
            },
        )
    assert imported.root.reused is False
    assert imported.root.document[0]["rich_text"][0]["text"] == "fresh"
    assert any("/blocks/" in path for path in calls)


@pytest.mark.asyncio
async def test_import_walks_snapshot_children_and_databases(monkeypatch):
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path.endswith(f"/pages/{ROOT}"):
            return httpx.Response(200, json=_page_json(ROOT, "Brazil"), request=request)
        if request.url.path.endswith(f"/pages/{CHILD}"):
            return httpx.Response(200, json=_page_json(CHILD, "Child"), request=request)
        if request.url.path.endswith(f"/databases/{DATABASE}/query"):
            return httpx.Response(
                200, json={"results": [{"id": CHILD}], "has_more": False}, request=request
            )
        raise AssertionError(f"unexpected {request.url.path}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = NotionClient("token", http=http, min_interval_seconds=0.01)
        monkeypatch.setattr("pomogator.infrastructure.notion.client.asyncio.sleep", _no_sleep)
        imported = await client.import_country(
            ROOT,
            "brazil",
            "🌍",
            snapshots={
                ROOT: PageSnapshot(
                    last_edited_at=EDITED,
                    document=[{"type": "paragraph", "rich_text": [{"text": "root"}]}],
                    child_ids=(CHILD,),
                    database_ids=(DATABASE,),
                ),
                CHILD: PageSnapshot(
                    last_edited_at=EDITED,
                    document=[{"type": "paragraph", "rich_text": [{"text": "kid"}]}],
                ),
            },
        )
    assert imported.root.reused is True
    assert imported.root.children[0].reused is True
    assert imported.root.children[0].document[0]["rich_text"][0]["text"] == "kid"
    assert f"POST /v1/databases/{DATABASE}/query" in calls
    assert all("/blocks/" not in path for path in calls)


def test_build_page_snapshots_skips_pages_without_revision():
    parent_id = uuid4()
    child_id = uuid4()
    parent = SimpleNamespace(
        id=parent_id,
        parent_id=None,
        position=0,
        notion_page_id=ROOT,
        notion_last_edited_at=EDITED,
        document=[{"type": "divider"}],
        notion_database_ids=[DATABASE],
    )
    child = SimpleNamespace(
        id=child_id,
        parent_id=parent_id,
        position=0,
        notion_page_id=CHILD,
        notion_last_edited_at=None,
        document=[],
        notion_database_ids=[],
    )
    snapshots = build_page_snapshots([parent, child])  # type: ignore[arg-type]
    assert ROOT in snapshots
    assert CHILD not in snapshots
    assert snapshots[ROOT].child_ids == (CHILD,)
    assert snapshots[ROOT].database_ids == (DATABASE,)


async def _no_sleep(_seconds: float) -> None:
    return None
