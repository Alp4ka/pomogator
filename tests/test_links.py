import pytest
from uuid import uuid4

from pomogator.domain.links import remap_internal_links
from pomogator.infrastructure.notion.client import NotionClient


def test_remap_table_cell_internal_links():
    target = uuid4()
    notion_id = "3b345344c78780e9817cf27f963a1893"
    document = [
        {
            "type": "table",
            "rows": [
                [
                    [
                        {
                            "text": "Виза",
                            "link": {"type": "internal", "notion_page_id": notion_id},
                        }
                    ],
                    [{"text": "plain"}],
                ]
            ],
        }
    ]
    remap_internal_links(document, {notion_id: target})
    link = document[0]["rows"][0][0][0]["link"]
    assert link == {"type": "internal", "page_id": str(target)}
    assert "notion_page_id" not in link


def test_remap_drops_unknown_internal_links():
    document = [
        {
            "type": "paragraph",
            "rich_text": [
                {
                    "text": "gone",
                    "link": {"type": "internal", "notion_page_id": "a" * 32},
                }
            ],
        }
    ]
    remap_internal_links(document, {})
    assert "link" not in document[0]["rich_text"][0]


@pytest.mark.asyncio
async def test_rich_imports_page_mention_without_href():
    client = NotionClient(token="test")
    page_id = "3b345344-c787-80e9-817c-f27f963a1893"
    imported = await client._rich(
        [
            {
                "type": "mention",
                "plain_text": "Виза",
                "annotations": {},
                "mention": {"type": "page", "page": {"id": page_id}},
            }
        ]
    )
    assert imported[0]["link"] == {
        "type": "internal",
        "notion_page_id": "3b345344c78780e9817cf27f963a1893",
    }
