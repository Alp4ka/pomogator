import pytest
from pomogator.infrastructure.notion.client import NotionClient


def test_extracts_notion_page_id():
    assert (
        NotionClient.notion_page_id("https://notion.so/Demo-3b345344c78780e9817cf27f963a1893")
        == "3b345344c78780e9817cf27f963a1893"
    )


def test_external_link_has_no_notion_id():
    assert NotionClient.notion_page_id("https://example.com/abc") is None


def test_rejects_notion_lookalike_host():
    assert (
        NotionClient.notion_page_id(
            "https://notion.so.evil.example/3b345344c78780e9817cf27f963a1893"
        )
        is None
    )


def test_external_url_allowlist():
    assert NotionClient.safe_external_url("https://example.com/path") == "https://example.com/path"
    assert NotionClient.safe_external_url("javascript:alert(1)") is None
    assert NotionClient.safe_external_url("http://example.com") is None


def test_youtube_video_id_parsing():
    assert (
        NotionClient.youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "dQw4w9WgXcQ"
    )
    assert NotionClient.youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert (
        NotionClient.youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    )
    assert NotionClient.youtube_video_id("https://example.com/watch?v=dQw4w9WgXcQ") is None


def test_youtube_block_from_video_payload():
    client = NotionClient(token="test")
    block = client._media_url_block(
        {
            "type": "video",
            "video": {
                "type": "external",
                "external": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                "caption": [{"plain_text": "Demo"}],
            },
        }
    )
    assert block == {
        "type": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "caption": "Demo",
    }


@pytest.mark.asyncio
async def test_table_import_builds_rows(monkeypatch):
    client = NotionClient(token="test")

    async def fake_blocks(_block_id: str) -> list[dict]:
        return [
            {
                "type": "table_row",
                "table_row": {
                    "cells": [
                        [{"plain_text": "A1", "annotations": {}}],
                        [{"plain_text": "B1", "annotations": {}}],
                    ]
                },
            },
            {
                "type": "table_row",
                "table_row": {
                    "cells": [
                        [{"plain_text": "A2", "annotations": {}}],
                        [{"plain_text": "B2", "annotations": {}}],
                    ]
                },
            },
        ]

    monkeypatch.setattr(client, "_all_blocks", fake_blocks)
    imported = await client._table(
        {
            "id": "table-1",
            "type": "table",
            "table": {"has_column_header": True, "has_row_header": False, "table_width": 2},
        }
    )
    assert imported["type"] == "table"
    assert imported["has_column_header"] is True
    assert imported["rows"][0][0][0]["text"] == "A1"
    assert imported["rows"][1][1][0]["text"] == "B2"
