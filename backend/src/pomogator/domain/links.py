"""Resolve Notion page ids in document rich text to internal page UUIDs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID


def iter_rich_sequences(document: list[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    """Yield every rich-text list stored in a page document (incl. table cells)."""
    for block in document:
        rich = block.get("rich_text")
        if isinstance(rich, list):
            yield rich
        rows = block.get("rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            for cell in row:
                if isinstance(cell, list):
                    yield cell
                elif isinstance(cell, dict):
                    cell_rich = cell.get("rich_text")
                    if isinstance(cell_rich, list):
                        yield cell_rich
                    cell_runs = cell.get("runs")
                    if isinstance(cell_runs, list):
                        yield cell_runs


def remap_internal_links(
    document: list[dict[str, Any]], known: dict[str, UUID]
) -> list[dict[str, Any]]:
    """Rewrite internal links from notion_page_id → page_id; drop unresolved ones."""
    for rich in iter_rich_sequences(document):
        for part in rich:
            if not isinstance(part, dict):
                continue
            link = part.get("link")
            if not isinstance(link, dict) or link.get("type") != "internal":
                continue
            notion_page_id = str(link.pop("notion_page_id", "") or "")
            existing = link.get("page_id")
            if existing:
                continue
            if target := known.get(notion_page_id):
                link["page_id"] = str(target)
            else:
                part.pop("link", None)
    return document
