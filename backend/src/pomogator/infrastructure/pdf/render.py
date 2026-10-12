"""Render page documents to PDF with multi-channel forensic stamps."""

from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from reportlab.lib.colors import Color, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from pomogator.domain.pdf_trace import disguise_token

_SAFE_NAME = re.compile(r"[^\w\s\-а-яА-ЯёЁ]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")
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
_EMOJI_CANDIDATES = (
    _FONTS_DIR / "NotoEmoji-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf"),
)
_SYMBOL_CANDIDATES = (
    _FONTS_DIR / "NotoSansSymbols2-Regular.ttf",
    Path("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"),
)

_CHECK_ON = "☑"
_CHECK_OFF = "☐"
_VS = frozenset({"\ufe0e", "\ufe0f"})
_ZWJ = "\u200d"
_INK = Color(0.10, 0.11, 0.14)
_MUTED = Color(0.36, 0.40, 0.45)
_WASH = Color(0.96, 0.96, 0.97)
_LINE = Color(0.89, 0.90, 0.92)
_ACCENT = Color(0.11, 0.73, 0.47)

Run = tuple[str, bool]


@lru_cache(maxsize=1)
def _register_fonts() -> tuple[str, str, tuple[str, ...]]:
    regular = "Helvetica"
    bold = "Helvetica-Bold"
    extras: list[str] = []
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
    for path in _EMOJI_CANDIDATES:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("GuideEmoji", str(path)))
            extras.append("GuideEmoji")
            break
    for path in _SYMBOL_CANDIDATES:
        if path.is_file():
            pdfmetrics.registerFont(TTFont("GuideSymbols", str(path)))
            extras.append("GuideSymbols")
            break
    return regular, bold, tuple(extras)


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


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", text.replace("\xa0", " ")).strip()


def _plain(
    rich: list[dict[str, Any]] | None,
    field_values: dict[str, str] | None = None,
) -> str:
    return _clean("".join(text for text, _bold in _style_runs(rich, field_values)))


def _style_runs(
    rich: list[dict[str, Any]] | None,
    field_values: dict[str, str] | None = None,
    *,
    default_bold: bool = False,
) -> list[Run]:
    if not rich:
        return []
    values = field_values or {}
    runs: list[Run] = []
    for part in rich:
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        raw_annotations = part.get("annotations")
        annotations = raw_annotations if isinstance(raw_annotations, dict) else {}
        bold = default_bold or bool(annotations.get("bold"))
        if kind == "checkbox":
            key = str(part.get("key") or "")
            raw = values.get(key)
            if raw is None:
                raw = str(part.get("default") or "false")
            runs.append((_CHECK_ON if _truthy(raw) else _CHECK_OFF, bold))
            continue
        if kind == "input":
            key = str(part.get("key") or "")
            current = (values.get(key) if key in values else "") or ""
            current = current.strip()
            if current:
                runs.append((current, bold))
                continue
            placeholder = str(part.get("placeholder") or "").strip()
            width = max(4, min(40, int(part.get("width") or 10)))
            runs.append((f"[{placeholder}]" if placeholder else ("_" * width), bold))
            continue
        if kind == "nav_label":
            continue
        text = str(part.get("text", ""))
        if text:
            runs.append((text, bold))
    return _merge_runs(runs)


def _merge_runs(runs: list[Run]) -> list[Run]:
    merged: list[Run] = []
    for text, bold in runs:
        if merged and merged[-1][1] == bold:
            merged[-1] = (merged[-1][0] + text, bold)
        else:
            merged.append((text, bold))
    return merged


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


def split_callout_text(items: list[dict[str, Any]] | None) -> tuple[str, str]:
    rich = [part for part in (items or []) if isinstance(part, dict)]
    first = rich[0] if rich else None
    first_text = _clean(str(first.get("text", ""))) if first else ""
    raw_annotations = first.get("annotations") if first else None
    annotations = raw_annotations if isinstance(raw_annotations, dict) else {}
    if first and annotations.get("bold") and first_text:
        return first_text, _plain(rich[1:])
    full = _plain(rich)
    match = re.search(r"[.!?]\s", full)
    if match and 0 < match.start() <= 56:
        return full[: match.start()].strip(), full[match.end() :].strip()
    return full, ""


def render_page_pdf(
    *,
    title: str,
    document: list[dict[str, Any]],
    export_id: UUID,
    sealed_token: str,
    field_values: dict[str, str] | None = None,
) -> bytes:
    regular, bold, extras = _register_fonts()
    values = field_values or {}
    buffer = io.BytesIO()
    page_width, page_height = A4
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)
    pdf.setAuthor("Pomogator")
    pdf.setCreator("Pomogator")
    pdf.setSubject(str(export_id))
    pdf.setKeywords(disguise_token(sealed_token))
    pdf.setProducer(f"Skia/PDF m128 (docs/{export_id.hex[:12]})")

    left = 16 * mm
    right = page_width - 16 * mm
    top = page_height - 16 * mm
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

    def gap(amount: float = 8) -> None:
        nonlocal y
        y -= amount

    def draw_runs(
        runs: list[Run],
        *,
        size: float,
        leading: float,
        x: float | None = None,
        max_width: float | None = None,
        color: Color = _INK,
        default_bold: bool = False,
    ) -> None:
        nonlocal y
        origin = left if x is None else x
        box = width if max_width is None else max_width
        styled = [(text, flag or default_bold) for text, flag in runs]
        if not styled:
            styled = [("", default_bold)]
        for line in _wrap_runs(pdf, styled, size, box, regular, bold, extras):
            ensure(leading)
            _draw_run_line(pdf, origin, y, line, size, regular, bold, extras, color)
            y -= leading

    def draw_text(
        text: str,
        *,
        size: float,
        leading: float,
        x: float | None = None,
        max_width: float | None = None,
        color: Color = _INK,
        as_bold: bool = False,
    ) -> None:
        draw_runs(
            [(text, as_bold)],
            size=size,
            leading=leading,
            x=x,
            max_width=max_width,
            color=color,
        )

    ensure(24)
    draw_text(_clean(title), size=18, leading=22, as_bold=True)
    gap(10)

    for block in document:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type") or "paragraph")
        parts = _block_runs(block)
        runs = _style_runs(parts, values)
        text = _plain(parts, values)

        if kind == "divider":
            numbered = 0
            ensure(16)
            pdf.setStrokeColor(_LINE)
            pdf.setLineWidth(0.7)
            pdf.line(left, y, right, y)
            gap(12)
            continue
        if kind == "image":
            numbered = 0
            caption = _clean(str(block.get("caption") or "изображение"))
            _draw_caption_box(pdf, left, y, width, 36, f"Изображение · {caption}", regular, extras)
            y -= 44
            continue
        if kind in {"youtube", "video"}:
            numbered = 0
            label = _clean(
                str(block.get("caption") or block.get("url") or block.get("video_id") or "YouTube")
            )
            _draw_caption_box(pdf, left, y, width, 28, f"Видео · {label}", regular, extras)
            y -= 36
            continue
        if kind == "table":
            numbered = 0
            rows_raw = block.get("rows") or []
            table_rows: list[list[str]] = []
            for row in rows_raw:
                if not isinstance(row, list):
                    continue
                table_rows.append(
                    [_cell_text(cell, values) or " " for cell in row]
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
                    regular=regular,
                    bold=bold,
                    extras=extras,
                    new_page=new_page,
                )
                gap(10)
            continue
        if kind == "code":
            numbered = 0
            lines = _wrap(pdf, text or " ", regular, 9, width - 16, extras) or [""]
            height = 14 + len(lines) * 12
            ensure(height)
            pdf.setFillColor(_WASH)
            pdf.roundRect(left, y - height + 8, width, height, 6, fill=1, stroke=0)
            y -= 10
            draw_text(text or " ", size=9, leading=12, x=left + 8, max_width=width - 16, color=_INK)
            gap(8)
            continue
        if kind == "callout":
            numbered = 0
            icon = str(block.get("icon") or "•").strip() or "•"
            title_text, body_text = split_callout_text(parts)
            title_text = title_text or text
            y = _draw_callout(
                pdf,
                x=left,
                y=y,
                width=width,
                bottom=bottom,
                page_top=top,
                icon=icon,
                title=title_text,
                body=body_text,
                regular=regular,
                bold=bold,
                extras=extras,
                new_page=new_page,
            )
            gap(8)
            continue
        if kind == "quote":
            numbered = 0
            quote_lines = _wrap(pdf, text or " ", regular, 11, width - 16, extras) or [""]
            height = 10 + len(quote_lines) * 15
            ensure(height)
            pdf.setStrokeColor(_ACCENT)
            pdf.setLineWidth(2.2)
            pdf.line(left + 1, y + 2, left + 1, y - height + 10)
            draw_text(
                text or " ",
                size=11,
                leading=15,
                x=left + 12,
                max_width=width - 16,
                color=_MUTED,
            )
            gap(8)
            continue
        if kind.startswith("heading_"):
            numbered = 0
            level = int(kind[-1]) if kind[-1].isdigit() else 2
            size = {1: 16, 2: 14, 3: 12, 4: 11}.get(level, 12)
            gap(8 if level <= 2 else 5)
            draw_runs(runs or [(text, True)], size=size, leading=size + 5, default_bold=True)
            gap(3)
            continue
        if kind == "bulleted_list_item":
            numbered = 0
            ensure(16)
            pdf.setFillColor(_ACCENT)
            pdf.circle(left + 3.5, y + 3, 2.1, fill=1, stroke=0)
            draw_runs(
                runs or [(text, False)],
                size=11,
                leading=15,
                x=left + 12,
                max_width=width - 12,
            )
            continue
        if kind == "numbered_list_item":
            numbered += 1
            ensure(20)
            _draw_index_chip(pdf, left, y, numbered, regular, extras)
            draw_runs(
                runs or [(text, False)],
                size=11,
                leading=15,
                x=left + 22,
                max_width=width - 22,
            )
            gap(2)
            continue
        if kind == "to_do":
            numbered = 0
            mark = _CHECK_ON if block.get("checked") else _CHECK_OFF
            draw_runs([(f"{mark} ", False), *runs], size=11, leading=15)
            continue

        numbered = 0
        if text:
            draw_runs(runs, size=11, leading=16)
            gap(5)

    _stamp_invisible(pdf, page_width, sealed_token, export_id)
    pdf.save()
    return buffer.getvalue()


def _stamp_invisible(
    pdf: canvas.Canvas, page_width: float, sealed_token: str, export_id: UUID
) -> None:
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
        return code < 256
    return code in glyphs


def _clusters(text: str) -> list[str]:
    chars = [char for char in text if char not in _VS]
    clusters: list[str] = []
    index = 0
    while index < len(chars):
        char = chars[index]
        if _is_regional(char) and index + 1 < len(chars) and _is_regional(chars[index + 1]):
            clusters.append(char + chars[index + 1])
            index += 2
            continue
        cluster = char
        index += 1
        while index < len(chars) and chars[index] == _ZWJ:
            cluster += chars[index]
            index += 1
            if index < len(chars):
                cluster += chars[index]
                index += 1
        clusters.append(cluster)
    return clusters


def _is_regional(char: str) -> bool:
    return 0x1F1E6 <= ord(char) <= 0x1F1FF


def _flag_iso(cluster: str) -> str | None:
    if len(cluster) != 2 or not (_is_regional(cluster[0]) and _is_regional(cluster[1])):
        return None
    return "".join(chr(ord(char) - 0x1F1E6 + 65) for char in cluster)


def _flag_badge_width(size: float) -> float:
    return size * 1.7 + 3


def _pick_font(cluster: str, primary: str, extras: tuple[str, ...]) -> str | None:
    stack = (primary, *extras)
    for font in stack:
        if all(_font_has_char(font, char) for char in cluster if char != _ZWJ):
            return font
    for font in extras:
        if any(_font_has_char(font, char) for char in cluster):
            return font
    return None


def _segments_for_fonts(
    text: str, primary: str, extras: tuple[str, ...] | str | None
) -> list[tuple[str, str]]:
    fallbacks = extras if isinstance(extras, tuple) else ((extras,) if extras else ())
    if not text:
        return []
    segments: list[tuple[str, str]] = []
    current_font: str | None = None
    buf = ""
    for cluster in _clusters(text):
        font = _pick_font(cluster, primary, fallbacks)
        if font is None:
            continue
        if font == current_font:
            buf += cluster
            continue
        if current_font and buf:
            segments.append((current_font, buf))
        current_font = font
        buf = cluster
    if current_font and buf:
        segments.append((current_font, buf))
    return segments


def _string_width(
    pdf: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    extras: tuple[str, ...] | str | None,
) -> float:
    total = 0.0
    for cluster in _clusters(text):
        if _flag_iso(cluster):
            total += _flag_badge_width(size)
            continue
        for use_font, chunk in _segments_for_fonts(cluster, font, extras):
            total += pdf.stringWidth(chunk, use_font, size)
    return total


def _draw_flag_badge(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    code: str,
    size: float,
    regular: str,
    extras: tuple[str, ...] | str | None,
) -> float:
    width = _flag_badge_width(size)
    height = size * 0.95
    pdf.setFillColor(Color(0.90, 0.96, 0.93))
    pdf.roundRect(x, y - size * 0.15, width - 2, height, 2.2, fill=1, stroke=0)
    label_width = pdf.stringWidth(code, regular, size * 0.62)
    _draw_mixed_string(
        pdf,
        x + (width - 2 - label_width) / 2,
        y,
        code,
        regular,
        size * 0.62,
        extras,
        Color(0.11, 0.45, 0.34),
    )
    return width


def _draw_mixed_string(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    font: str,
    size: float,
    extras: tuple[str, ...] | str | None,
    color: Color = _INK,
) -> None:
    pdf.setFillColor(color)
    cursor = x
    for cluster in _clusters(text):
        code = _flag_iso(cluster)
        if code:
            cursor += _draw_flag_badge(pdf, cursor, y, code, size, font, extras)
            continue
        for use_font, chunk in _segments_for_fonts(cluster, font, extras):
            pdf.setFillColor(color)
            pdf.setFont(use_font, size)
            pdf.drawString(cursor, y, chunk)
            cursor += pdf.stringWidth(chunk, use_font, size)


def _wrap(
    pdf: canvas.Canvas,
    text: str,
    font: str,
    size: float,
    max_width: float,
    extras: tuple[str, ...] | str | None = None,
) -> list[str]:
    cleaned = _clean(text)
    if not cleaned:
        return [""]
    words = cleaned.split(" ")
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _string_width(pdf, candidate, font, size, extras) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if _string_width(pdf, word, font, size, extras) <= max_width:
            current = word
            continue
        overflow, rest = _split_long_word(pdf, word, font, size, max_width, extras)
        lines.extend(overflow)
        current = rest
    if current:
        lines.append(current)
    return lines or [""]


def _split_long_word(
    pdf: canvas.Canvas,
    word: str,
    font: str,
    size: float,
    max_width: float,
    extras: tuple[str, ...] | str | None,
) -> tuple[list[str], str]:
    pieces: list[str] = []
    current = ""
    for cluster in _clusters(word):
        candidate = current + cluster
        if current and _string_width(pdf, candidate, font, size, extras) > max_width:
            pieces.append(current)
            current = cluster
        else:
            current = candidate
    return pieces, current


def _wrap_runs(
    pdf: canvas.Canvas,
    runs: list[Run],
    size: float,
    max_width: float,
    regular: str,
    bold: str,
    extras: tuple[str, ...],
) -> list[list[Run]]:
    tokens: list[Run] = []
    for text, is_bold in runs:
        cleaned = _WHITESPACE.sub(" ", text.replace("\xa0", " "))
        if not cleaned:
            continue
        pieces = re.findall(r"\S+\s*", cleaned)
        for piece in pieces:
            tokens.append((piece, is_bold))
    if not tokens:
        return [[("", False)]]

    def token_width(item: Run) -> float:
        face = bold if item[1] else regular
        return _string_width(pdf, item[0], face, size, extras)

    lines: list[list[Run]] = []
    current: list[Run] = []
    current_width = 0.0
    for token in tokens:
        width = token_width(token)
        if current and current_width + width > max_width:
            lines.append(_trim_runs(current))
            current = [(token[0].lstrip(), token[1])]
            current_width = token_width(current[0])
            continue
        current.append(token)
        current_width += width
    if current:
        lines.append(_trim_runs(current))
    return lines or [[("", False)]]


def _trim_runs(runs: list[Run]) -> list[Run]:
    if not runs:
        return [("", False)]
    first = runs[0][0].lstrip()
    last = runs[-1][0].rstrip()
    out = list(runs)
    out[0] = (first, out[0][1])
    out[-1] = (last, out[-1][1])
    return [(text, bold) for text, bold in out if text]


def _draw_run_line(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    runs: list[Run],
    size: float,
    regular: str,
    bold: str,
    extras: tuple[str, ...],
    color: Color,
) -> None:
    cursor = x
    for text, is_bold in runs:
        face = bold if is_bold else regular
        _draw_mixed_string(pdf, cursor, y, text, face, size, extras, color)
        cursor += _string_width(pdf, text, face, size, extras)


def _draw_caption_box(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    regular: str,
    extras: tuple[str, ...],
) -> None:
    pdf.setFillColor(_WASH)
    pdf.roundRect(x, y - height + 10, width, height, 8, fill=1, stroke=0)
    _draw_mixed_string(pdf, x + 10, y - 8, label, regular, 9, extras, _MUTED)


def _draw_index_chip(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    number: int,
    regular: str,
    extras: tuple[str, ...],
) -> None:
    pdf.setFillColor(Color(0.91, 0.97, 0.93))
    pdf.circle(x + 8, y + 3, 8, fill=1, stroke=0)
    label = str(number)
    width = _string_width(pdf, label, regular, 8, extras)
    _draw_mixed_string(
        pdf,
        x + 8 - width / 2,
        y,
        label,
        regular,
        8,
        extras,
        Color(0.11, 0.56, 0.42),
    )


def _draw_callout(
    pdf: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    bottom: float,
    page_top: float,
    icon: str,
    title: str,
    body: str,
    regular: str,
    bold: str,
    extras: tuple[str, ...],
    new_page: Any,
) -> float:
    text_x = x + 36
    text_width = width - 46
    title_lines = _wrap(pdf, title, bold, 11, text_width, extras) if title else []
    body_lines = _wrap(pdf, body, regular, 10, text_width, extras) if body else []
    height = 18 + len(title_lines) * 14 + len(body_lines) * 13
    if y - height < bottom:
        new_page()
        y = page_top
    pdf.setFillColor(_WASH)
    pdf.roundRect(x, y - height + 10, width, height, 8, fill=1, stroke=0)
    pdf.setFillColor(Color(0.91, 0.97, 0.93))
    pdf.circle(x + 18, y - 8, 11, fill=1, stroke=0)
    _draw_mixed_string(pdf, x + 11, y - 12, icon, regular, 12, extras)
    cursor = y - 6
    for line in title_lines:
        _draw_mixed_string(pdf, text_x, cursor, line, bold, 11, extras, _INK)
        cursor -= 14
    for line in body_lines:
        _draw_mixed_string(pdf, text_x, cursor, line, regular, 10, extras, _MUTED)
        cursor -= 13
    return y - height + 4


def _draw_table(
    pdf: canvas.Canvas,
    *,
    rows: list[list[str]],
    x: float,
    y: float,
    max_width: float,
    bottom: float,
    page_top: float,
    regular: str,
    bold: str,
    extras: tuple[str, ...],
    new_page: Any,
) -> float:
    if not rows:
        return y
    cols = max(len(row) for row in rows)
    if cols == 0:
        return y
    normalized = [row + [""] * (cols - len(row)) for row in rows]
    size = 9.5
    leading = 12.5
    pad = 6.0
    weights = [0.0] * cols
    for row in normalized:
        for index, cell in enumerate(row):
            weights[index] = max(weights[index], min(48.0, max(8.0, len(cell) * 0.7)))
    total = sum(weights) or cols
    col_widths = [max(36.0, max_width * (weight / total)) for weight in weights]
    scale = max_width / sum(col_widths)
    col_widths = [width * scale for width in col_widths]

    wrapped_rows: list[list[list[str]]] = []
    row_heights: list[float] = []
    for row in normalized:
        wrapped = [
            _wrap(pdf, cell, regular, size, max(24.0, col_widths[index] - 2 * pad), extras) or [""]
            for index, cell in enumerate(row)
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
        if row_index == 0:
            pdf.setFillColor(_WASH)
            pdf.rect(x, bottom_y, max_width, height, stroke=0, fill=1)
        pdf.setStrokeColor(_LINE)
        pdf.setLineWidth(0.6)
        pdf.rect(x, bottom_y, max_width, height, stroke=1, fill=0)
        line_x = x
        for col in range(cols - 1):
            line_x += col_widths[col]
            pdf.line(line_x, bottom_y, line_x, top_y)
        text_x = x
        face = bold if row_index == 0 else regular
        for col, lines in enumerate(wrapped):
            text_y = top_y - pad - size
            for line in lines:
                _draw_mixed_string(pdf, text_x + pad, text_y, line, face, size, extras, _INK)
                text_y -= leading
            text_x += col_widths[col]
        cursor_y = bottom_y
    return cursor_y
