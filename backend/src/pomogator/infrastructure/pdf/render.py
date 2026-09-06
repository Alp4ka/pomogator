"""Render page documents to PDF with multi-channel forensic stamps."""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pomogator.domain.pdf_trace import disguise_token

_SAFE_NAME = re.compile(r"[^\w\s\-а-яА-ЯёЁ]+", re.UNICODE)
_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
)
_BOLD_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
)


@lru_cache(maxsize=1)
def _register_fonts() -> tuple[str, str]:
    regular = "Helvetica"
    bold = "Helvetica-Bold"
    for path in _FONT_CANDIDATES:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("GuideSans", str(path)))
            regular = "GuideSans"
            break
    for path in _BOLD_CANDIDATES:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("GuideSans-Bold", str(path)))
            bold = "GuideSans-Bold"
            break
    if regular == "GuideSans" and bold == "Helvetica-Bold":
        bold = "GuideSans"
    return regular, bold


def filename_for_title(title: str) -> str:
    cleaned = _SAFE_NAME.sub("", title).strip() or "guide"
    return f"{cleaned[:80]}.pdf"


def _plain(rich: list[dict[str, Any]] | None) -> str:
    if not rich:
        return ""
    return "".join(str(part.get("text", "")) for part in rich)


def render_page_pdf(
    *,
    title: str,
    document: list[dict[str, Any]],
    export_id: UUID,
    sealed_token: str,
) -> bytes:
    regular, bold = _register_fonts()
    buffer = io.BytesIO()
    page_width, page_height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)
    pdf.setAuthor("Pomogator")
    pdf.setCreator("Pomogator")
    # Looks like a normal document UUID in PDF readers.
    pdf.setSubject(str(export_id))
    # Opaque build/cache style token — not labeled as user id.
    pdf.setKeywords(disguise_token(sealed_token))
    pdf.setProducer(f"Skia/PDF m128 (docs/{export_id.hex[:12]})")

    left = 18 * mm
    right = page_width - 18 * mm
    top = page_height - 18 * mm
    bottom = 16 * mm
    width = right - left
    y = top

    def new_page() -> None:
        nonlocal y
        _stamp_invisible(pdf, page_width, sealed_token, export_id)
        pdf.showPage()
        y = top

    def ensure(space: float) -> None:
        nonlocal y
        if y - space < bottom:
            new_page()

    def draw_wrapped(text: str, font: str, size: float, leading: float) -> None:
        nonlocal y
        pdf.setFont(font, size)
        pdf.setFillColor(black)
        for line in _wrap(pdf, text, font, size, width):
            ensure(leading)
            pdf.drawString(left, y, line)
            y -= leading

    ensure(22)
    draw_wrapped(title, bold, 18, 22)
    y -= 8

    for block in document:
        kind = block.get("type", "paragraph")
        text = _plain(block.get("rich_text"))
        if kind == "divider":
            ensure(14)
            pdf.setStrokeColor(Color(0.75, 0.75, 0.75))
            pdf.setLineWidth(0.6)
            pdf.line(left, y, right, y)
            y -= 14
            continue
        if kind == "image":
            caption = block.get("caption") or "Image"
            draw_wrapped(f"[image] {caption}", regular, 10, 13)
            y -= 4
            continue
        if kind == "youtube" or kind == "video":
            label = block.get("caption") or block.get("url") or block.get("video_id") or "YouTube"
            draw_wrapped(f"[youtube] {label}", regular, 10, 13)
            y -= 4
            continue
        if kind == "table":
            rows = block.get("rows") or []
            for row in rows:
                cells = [
                    _plain(cell) if isinstance(cell, list) else str(cell)
                    for cell in row
                ]
                draw_wrapped(" | ".join(cells) or " ", regular, 9, 12)
            y -= 4
            continue
        if kind == "code":
            ensure(16)
            pdf.setFillColor(Color(0.95, 0.95, 0.95))
            pdf.rect(left - 2, y - 12, width + 4, 16, fill=1, stroke=0)
            draw_wrapped(text or " ", regular, 9, 11)
            y -= 6
            continue
        if kind == "callout":
            icon = block.get("icon") or "-"
            draw_wrapped(f"{icon} {text}", bold, 11, 15)
            y -= 4
            continue
        if kind == "quote":
            draw_wrapped(text, regular, 11, 15)
            y -= 4
            continue
        if kind.startswith("heading_"):
            level = int(kind[-1]) if kind[-1].isdigit() else 2
            size = {1: 16, 2: 14, 3: 12, 4: 11}.get(level, 12)
            y -= 6
            draw_wrapped(text, bold, size, size + 4)
            y -= 2
            continue
        if kind == "bulleted_list_item":
            draw_wrapped(f"- {text}", regular, 11, 15)
            continue
        if kind == "numbered_list_item":
            draw_wrapped(f"* {text}", regular, 11, 15)
            continue
        if kind == "to_do":
            mark = "[x]" if block.get("checked") else "[ ]"
            draw_wrapped(f"{mark} {text}", regular, 11, 15)
            continue
        if text:
            draw_wrapped(text, regular, 11, 15)
            y -= 2

    _stamp_invisible(pdf, page_width, sealed_token, export_id)
    pdf.save()
    return buffer.getvalue()


def _stamp_invisible(
    pdf: canvas.Canvas, page_width: float, sealed_token: str, export_id: UUID
) -> None:
    # Near-white microtype near the page edge — not noticeable at normal zoom.
    pdf.saveState()
    pdf.setFillColor(Color(0.99, 0.99, 0.99))
    pdf.setFont("Helvetica", 0.5)
    pdf.drawString(2 * mm, 2 * mm, disguise_token(sealed_token))
    pdf.setFillColor(white)
    pdf.setFont("Helvetica", 0.01)
    pdf.drawRightString(page_width - 2 * mm, 1 * mm, str(export_id))
    pdf.restoreState()


def _wrap(pdf: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdf.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
