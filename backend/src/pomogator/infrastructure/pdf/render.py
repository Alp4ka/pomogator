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
_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_FONT_CANDIDATES = (
    _FONTS_DIR / "DejaVuSans.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
)
_BOLD_CANDIDATES = (
    _FONTS_DIR / "DejaVuSans-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
)
_SYMBOL_CANDIDATES = (
    _FONTS_DIR / "NotoSansSymbols2-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"),
)

_CHECK_ON = "☑"
_CHECK_OFF = "☐"


@lru_cache(maxsize=1)
def _register_fonts() -> tuple[str, str, str | None]:
    regular = "Helvetica"
    bold = "Helvetica-Bold"
    symbols: str | None = None
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
    for path in _SYMBOL_CANDIDATES:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("GuideSymbols", str(path)))
            symbols = "GuideSymbols"
            break
    return regular, bold, symbols


@lru_cache(maxsize=8)
def _font_glyph_map(font_name: str) -> frozenset[int]:
    font = pdfmetrics.getFont(font_name)
    face = getattr(font, "face", None)
    mapping = getattr(face, "charToGlyph", None) if face is not None else None
    if isinstance(mapping, dict) and mapping:
        return frozenset(int(code) for code in mapping)
    return frozenset()


def filename_for_title(title: str) -> str:
    cleaned = _SAFE_NAME.sub("", title).strip() or "guide"
    return f"{cleaned[:80]}.pdf"


def _truthy(value: str | None) -> bool:
    token = (value or "").strip().casefold()
    return token in {"1", "true", "yes", "on", "checked", "да", "вкл"}


def _plain(
    rich: list[dict[str, Any]] | None,
    field_values: dict[str, str] | None = None,
) -> str:
    if not rich:
        return ""
    values = field_values or {}
    parts: list[str] = []
    for part in rich:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind == "checkbox":
            key = str(part.get("key") or "")
            raw = values.get(key)
            if raw is None:
                raw = str(part.get("default") or "false")
            parts.append(_CHECK_ON if _truthy(raw) else _CHECK_OFF)
            continue
        if kind == "input":
            key = str(part.get("key") or "")
            current = values.get(key)
            if current is None:
                current = ""
            current = current.strip()
            if current:
                parts.append(current)
                continue
            placeholder = str(part.get("placeholder") or "").strip()
            width = int(part.get("width") or 10)
            width = max(4, min(40, width))
            parts.append(f"[{placeholder}]" if placeholder else ("_" * width))
            continue
        if kind == "nav_label":
            continue
        parts.append(str(part.get("text", "")))
    return "".join(parts)


def _block_runs(block: dict[str, Any]) -> list[dict[str, Any]]:
    runs = block.get("runs")
    if isinstance(runs, list) and runs:
        return [run for run in runs if isinstance(run, dict)]
    rich = block.get("rich_text")
    if isinstance(rich, list):
        return [part for part in rich if isinstance(part, dict)]
    return []


def _cell_text(cell: object, field_values: dict[str, str] | None = None) -> str:
    """Plain text for a table cell (list of rich parts or annotated dict)."""
    if isinstance(cell, list):
        return _plain(cell, field_values)
    if isinstance(cell, dict):
        runs = cell.get("runs")
        if isinstance(runs, list) and runs:
            return _plain(runs, field_values)
        rich = cell.get("rich_text")
        if isinstance(rich, list):
            return _plain(rich, field_values)
        return ""
    return ""


def render_page_pdf(
    *,
    title: str,
    document: list[dict[str, Any]],
    export_id: UUID,
    sealed_token: str,
    field_values: dict[str, str] | None = None,
) -> bytes:
    regular, bold, symbols = _register_fonts()
    values = field_values or {}
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
    numbered = 0

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
        for line in _wrap(pdf, text, font, size, width, symbols):
            ensure(leading)
            _draw_mixed_string(pdf, left, y, line, font, size, symbols)
            y -= leading

    ensure(22)
    draw_wrapped(title, bold, 18, 22)
    y -= 8

    for block in document:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "paragraph")
        text = _plain(_block_runs(block), values)

        if kind == "divider":
            numbered = 0
            ensure(14)
            pdf.setStrokeColor(Color(0.75, 0.75, 0.75))
            pdf.setLineWidth(0.6)
            pdf.line(left, y, right, y)
            y -= 14
            continue
        if kind == "image":
            numbered = 0
            caption = block.get("caption") or "Image"
            draw_wrapped(f"[изображение] {caption}", regular, 10, 13)
            y -= 4
            continue
        if kind in {"youtube", "video"}:
            numbered = 0
            label = block.get("caption") or block.get("url") or block.get("video_id") or "YouTube"
            draw_wrapped(f"[youtube] {label}", regular, 10, 13)
            y -= 4
            continue
        if kind == "table":
            numbered = 0
            rows_raw = block.get("rows") or []
            table_rows: list[list[str]] = []
            for row in rows_raw:
                if not isinstance(row, list):
                    continue
                table_rows.append(
                    [
                        _cell_text(cell, values).replace("\n", " ").strip() or " "
                        for cell in row
                    ]
                )
            if table_rows:
                y = _draw_table(
                    pdf,
                    rows=table_rows,
                    x=left,
                    y=y,
                    max_width=width,
                    bottom=bottom,
                    page_top=top,
                    font=regular,
                    symbols=symbols,
                    new_page=new_page,
                )
                y -= 8
            continue
        if kind == "code":
            numbered = 0
            ensure(16)
            pdf.setFillColor(Color(0.94, 0.94, 0.94))
            pdf.rect(left - 2, y - 12, width + 4, 16, fill=1, stroke=0)
            draw_wrapped(text or " ", regular, 9, 11)
            y -= 6
            continue
        if kind == "callout":
            numbered = 0
            icon = str(block.get("icon") or "•").strip() or "•"
            draw_wrapped(f"{icon} {text}".strip(), bold, 11, 15)
            y -= 4
            continue
        if kind == "quote":
            numbered = 0
            ensure(15)
            pdf.setStrokeColor(Color(0.7, 0.7, 0.7))
            pdf.setLineWidth(2)
            pdf.line(left, y + 2, left, y - 10)
            _draw_mixed_string(pdf, left + 8, y, text or " ", regular, 11, symbols)
            y -= 16
            continue
        if kind.startswith("heading_"):
            numbered = 0
            level = int(kind[-1]) if kind[-1].isdigit() else 2
            size = {1: 16, 2: 14, 3: 12, 4: 11}.get(level, 12)
            y -= 6
            draw_wrapped(text, bold, size, size + 4)
            y -= 2
            continue
        if kind == "bulleted_list_item":
            numbered = 0
            draw_wrapped(f"• {text}", regular, 11, 15)
            continue
        if kind == "numbered_list_item":
            numbered += 1
            draw_wrapped(f"{numbered}. {text}", regular, 11, 15)
            continue
        if kind == "to_do":
            numbered = 0
            mark = _CHECK_ON if block.get("checked") else _CHECK_OFF
            draw_wrapped(f"{mark} {text}", regular, 11, 15)
            continue

        numbered = 0
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


def _font_has_char(font_name: str, char: str) -> bool:
    if not char:
        return True
    code = ord(char)
    if code < 32:
        return True
    glyphs = _font_glyph_map(font_name)
    if not glyphs:
        # Built-in fonts: assume Latin only.
        return code < 256
    return code in glyphs


def _segments_for_fonts(
    text: str, primary: str, symbols: str | None
) -> list[tuple[str, str]]:
    if not text:
        return []
    if not symbols:
        return [(primary, text)]
    segments: list[tuple[str, str]] = []
    current_font = primary if _font_has_char(primary, text[0]) else symbols
    buf = text[0]
    for char in text[1:]:
        font = primary if _font_has_char(primary, char) else symbols
        if font == current_font:
            buf += char
        else:
            segments.append((current_font, buf))
            current_font = font
            buf = char
    segments.append((current_font, buf))
    return segments


def _string_width(
    pdf: canvas.Canvas, text: str, font: str, size: float, symbols: str | None
) -> float:
    total = 0.0
    for use_font, chunk in _segments_for_fonts(text, font, symbols):
        total += pdf.stringWidth(chunk, use_font, size)
    return total


def _draw_mixed_string(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    font: str,
    size: float,
    symbols: str | None,
) -> None:
    pdf.setFillColor(black)
    cursor = x
    for use_font, chunk in _segments_for_fonts(text, font, symbols):
        pdf.setFont(use_font, size)
        pdf.drawString(cursor, y, chunk)
        cursor += pdf.stringWidth(chunk, use_font, size)


def _wrap(
    pdf: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    max_width: float,
    symbols: str | None = None,
) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _string_width(pdf, candidate, font, size, symbols) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_table(
    pdf: canvas.Canvas,
    *,
    rows: list[list[str]],
    x: float,
    y: float,
    max_width: float,
    bottom: float,
    page_top: float,
    font: str,
    symbols: str | None,
    new_page: Any,
) -> float:
    if not rows:
        return y
    cols = max(len(row) for row in rows)
    if cols == 0:
        return y
    normalized = [row + [""] * (cols - len(row)) for row in rows]
    col_width = max_width / cols
    size = 9.0
    leading = 11.0
    pad = 4.0

    wrapped_rows: list[list[list[str]]] = []
    row_heights: list[float] = []
    for row in normalized:
        wrapped = [
            _wrap(pdf, cell, font, size, max(20.0, col_width - 2 * pad), symbols) or [""]
            for cell in row
        ]
        wrapped_rows.append(wrapped)
        row_heights.append(max(len(lines) for lines in wrapped) * leading + 2 * pad)

    cursor_y = y
    for row_index, wrapped in enumerate(wrapped_rows):
        height = row_heights[row_index]
        if cursor_y - height < bottom:
            new_page()
            cursor_y = page_top

        top_y = cursor_y
        bottom_y = cursor_y - height
        pdf.setStrokeColor(Color(0.75, 0.75, 0.75))
        pdf.setLineWidth(0.5)
        pdf.rect(x, bottom_y, max_width, height, stroke=1, fill=0)
        for col in range(1, cols):
            line_x = x + col * col_width
            pdf.line(line_x, bottom_y, line_x, top_y)

        for col, lines in enumerate(wrapped):
            text_x = x + col * col_width + pad
            text_y = top_y - pad - size
            for line in lines:
                _draw_mixed_string(pdf, text_x, text_y, line, font, size, symbols)
                text_y -= leading
        cursor_y = bottom_y
    return cursor_y
