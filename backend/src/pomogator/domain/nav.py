"""Pomogator Notion markup tags: in-page and cross-page navigation."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pomogator.domain.content import normalize_nav_label

_NAV_LABEL_TAG = re.compile(r"\{pmg\.nav\.label\(([^)]*)\)\}", re.IGNORECASE)
# Display text may be bare or wrapped in "..." / '...'
_NAV_GOTO_TAG = re.compile(
    r"\{pmg\.nav\.goto\(([^,)]+)\s*,\s*(?:\"([^\"]*)\"|'([^']*)'|(.*?))\)\}",
    re.IGNORECASE | re.DOTALL,
)
_NAV_GOTOPAGE_TAG = re.compile(
    r"\{pmg\.nav\.gotopage\(([^,)]+)\s*,\s*(?:\"([^\"]*)\"|'([^']*)'|(.*?))\)\}",
    re.IGNORECASE | re.DOTALL,
)

_NAV_ANY = re.compile(
    r"\{pmg\.nav\.(?:label\([^)]*\)|goto\([^)]*\)|gotopage\([^)]*\))\}",
    re.IGNORECASE | re.DOTALL,
)


def has_nav_tags(text: str) -> bool:
    return bool(_NAV_ANY.search(text))


_DISPLAY_QUOTE_PAIRS = (
    ('"', '"'),
    ("'", "'"),
    ("\u201c", "\u201d"),  # “ ”
    ("\u2018", "\u2019"),  # ‘ ’
    ("\u00ab", "\u00bb"),  # « »
)


def normalize_nav_display_text(*candidates: str | None) -> str | None:
    """Pick first non-empty display text; strip wrapping quotes if present."""
    for raw in candidates:
        if raw is None:
            continue
        text = raw.strip()
        if len(text) >= 2:
            for left, right in _DISPLAY_QUOTE_PAIRS:
                if text[0] == left and text[-1] == right:
                    text = text[1:-1].strip()
                    break
        if text:
            return text
    return None


def iter_nav_tag_spans(text: str) -> list[tuple[int, int, str, dict[str, str]]]:
    """Return (start, end, kind, payload) sorted by start for nav tags in text."""
    found: list[tuple[int, int, str, dict[str, str]]] = []
    for match in _NAV_LABEL_TAG.finditer(text):
        label = normalize_nav_label(match.group(1))
        if label:
            found.append((match.start(), match.end(), "nav_label", {"label": label}))
    for match in _NAV_GOTO_TAG.finditer(text):
        label = normalize_nav_label(match.group(1))
        display = normalize_nav_display_text(match.group(2), match.group(3), match.group(4))
        if label and display:
            found.append(
                (match.start(), match.end(), "nav_goto", {"label": label, "text": display})
            )
    for match in _NAV_GOTOPAGE_TAG.finditer(text):
        label = normalize_nav_label(match.group(1))
        display = normalize_nav_display_text(match.group(2), match.group(3), match.group(4))
        if label and display:
            found.append(
                (
                    match.start(),
                    match.end(),
                    "nav_gotopage",
                    {"label": label, "text": display},
                )
            )
    found.sort(key=lambda item: item[0])
    # Drop overlapping matches (keep earliest).
    filtered: list[tuple[int, int, str, dict[str, str]]] = []
    cursor = 0
    for start, end, kind, payload in found:
        if start < cursor:
            continue
        filtered.append((start, end, kind, payload))
        cursor = end
    return filtered


def resolve_nav_in_document(
    document: list[dict[str, Any]], page_by_label: dict[str, UUID]
) -> list[dict[str, Any]]:
    """Attach block nav_anchor and resolve goto/gotopage links (casefold labels)."""
    page_index = {key.casefold(): value for key, value in page_by_label.items()}
    anchors: set[str] = set()

    def visit_runs(runs: list[dict[str, Any]] | None) -> str | None:
        if not isinstance(runs, list):
            return None
        first_anchor: str | None = None
        for run in runs:
            if not isinstance(run, dict):
                continue
            if run.get("type") == "nav_label":
                label = normalize_nav_label(str(run.get("label") or ""))
                if label:
                    anchors.add(label.casefold())
                    if first_anchor is None:
                        first_anchor = label
        return first_anchor

    for block in document:
        if not isinstance(block, dict):
            continue
        anchor = visit_runs(block.get("runs") if isinstance(block.get("runs"), list) else None)
        if anchor:
            block["nav_anchor"] = anchor
        if block.get("type") == "table" and isinstance(block.get("rows"), list):
            for row in block["rows"]:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    if not isinstance(cell, dict):
                        continue
                    cell_anchor = visit_runs(cell.get("runs"))
                    if cell_anchor:
                        cell["nav_anchor"] = cell_anchor

    def resolve_run(run: dict[str, Any]) -> None:
        if run.get("type") != "text":
            return
        if goto := run.pop("nav_goto", None):
            label = normalize_nav_label(str(goto))
            if label and label.casefold() in anchors:
                run["link"] = {"type": "anchor", "label": label}
            else:
                run.pop("link", None)
        if gotopage := run.pop("nav_gotopage", None):
            label = normalize_nav_label(str(gotopage))
            target = page_index.get(label.casefold()) if label else None
            if target:
                run["link"] = {"type": "internal", "page_id": str(target)}
            else:
                run.pop("link", None)

    def resolve_runs(runs: list[dict[str, Any]] | None) -> None:
        if not isinstance(runs, list):
            return
        # Drop invisible nav_label runs from client payload.
        cleaned = [
            run
            for run in runs
            if not (isinstance(run, dict) and run.get("type") == "nav_label")
        ]
        runs[:] = cleaned
        for run in runs:
            if isinstance(run, dict):
                resolve_run(run)

    for block in document:
        if not isinstance(block, dict):
            continue
        resolve_runs(block.get("runs") if isinstance(block.get("runs"), list) else None)
        # Mirror resolved links into rich_text for consumers that only read rich_text.
        if isinstance(block.get("runs"), list) and isinstance(block.get("rich_text"), list):
            block["rich_text"] = [
                {
                    "text": run.get("text", ""),
                    "annotations": run.get("annotations") or {},
                    **({"link": run["link"]} if run.get("link") else {}),
                }
                for run in block["runs"]
                if isinstance(run, dict) and run.get("type") == "text"
            ]
        if block.get("type") == "table" and isinstance(block.get("rows"), list):
            for row in block["rows"]:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    if not isinstance(cell, dict):
                        continue
                    resolve_runs(cell.get("runs") if isinstance(cell.get("runs"), list) else None)
                    if isinstance(cell.get("runs"), list):
                        cell["rich_text"] = [
                            {
                                "text": run.get("text", ""),
                                "annotations": run.get("annotations") or {},
                                **({"link": run["link"]} if run.get("link") else {}),
                            }
                            for run in cell["runs"]
                            if isinstance(run, dict) and run.get("type") == "text"
                        ]
    return document
