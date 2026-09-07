"""Pomogator Notion markup tags: interactive fields + nav tags."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from pomogator.domain.nav import has_nav_tags, iter_nav_tag_spans, resolve_nav_in_document

# Legacy: {pmg.field.input({24,placeholder})}  and plain: {pmg.field.input(24, placeholder)}
_INPUT_TAG = re.compile(
    r"\{pmg\.field\.input\("
    r"(?:"
    r"\{(\d+)\s*,\s*(.*?)\}"  # braced args
    r"|"
    r"(\d+)\s*,\s*(.*?)"  # plain args; placeholder may be empty
    r")"
    r"\)\}",
    re.IGNORECASE | re.DOTALL,
)
_CB_TAG = re.compile(r"\{pmg\.field\.cb\(([^)]*)\)\}", re.IGNORECASE)
_FIELD_PATTERN = re.compile(
    r"\{pmg\.field\.input\("
    r"(?:"
    r"\{(\d+)\s*,\s*(.*?)\}"
    r"|"
    r"(\d+)\s*,\s*(.*?)"
    r")"
    r"\)\}"
    r"|"
    r"\{pmg\.field\.cb\(([^)]*)\)\}",
    re.IGNORECASE | re.DOTALL,
)

FieldKind = Literal["input", "checkbox"]
MAX_FIELD_VALUE_LEN = 2000


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    kind: FieldKind
    default: str
    width: int | None = None
    placeholder: str = ""


def parse_checkbox_default(raw: str) -> bool:
    token = raw.strip().casefold()
    if token in {"", "0", "false", "no", "off", "unchecked", "нет", "выкл"}:
        return False
    if token in {"1", "true", "yes", "on", "checked", "да", "вкл"}:
        return True
    return False


def field_key(kind: FieldKind, signature: str, occurrence: int) -> str:
    material = f"{kind}\0{occurrence}\0{signature}".encode()
    return hashlib.sha256(material).hexdigest()[:24]


def normalize_field_value(kind: FieldKind, value: str) -> str:
    if kind == "checkbox":
        return "true" if parse_checkbox_default(value) else "false"
    return value[:MAX_FIELD_VALUE_LEN]


def _text_run(text: str, base: dict[str, Any], **extra: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "type": "text",
        "text": text,
        "annotations": dict(base.get("annotations") or {}),
    }
    if base.get("link") and "nav_goto" not in extra and "nav_gotopage" not in extra:
        run["link"] = base["link"]
    run.update(extra)
    return run


def _merge_adjacent_text(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not runs:
        return []
    merged: list[dict[str, Any]] = [dict(runs[0])]
    for run in runs[1:]:
        prev = merged[-1]
        if (
            prev.get("type") == "text"
            and run.get("type") == "text"
            and prev.get("annotations") == run.get("annotations")
            and prev.get("link") == run.get("link")
            and prev.get("nav_goto") == run.get("nav_goto")
            and prev.get("nav_gotopage") == run.get("nav_gotopage")
        ):
            prev["text"] = str(prev.get("text", "")) + str(run.get("text", ""))
        else:
            merged.append(dict(run))
    return merged


def _field_spans(text: str) -> list[tuple[int, int, str, dict[str, Any]]]:
    spans: list[tuple[int, int, str, dict[str, Any]]] = []
    for match in _FIELD_PATTERN.finditer(text):
        if match.group(1) is not None or match.group(3) is not None:
            width_raw = match.group(1) if match.group(1) is not None else match.group(3)
            placeholder_raw = match.group(2) if match.group(1) is not None else match.group(4)
            width = max(1, min(120, int(width_raw or "1")))
            placeholder = (placeholder_raw or "").strip()
            spans.append(
                (
                    match.start(),
                    match.end(),
                    "input",
                    {"width": width, "placeholder": placeholder},
                )
            )
        else:
            default_raw = match.group(5) or ""
            spans.append(
                (match.start(), match.end(), "checkbox", {"default_raw": default_raw})
            )
    return spans


def _plain_runs_from_joined(
    joined: str, bases: list[dict[str, Any]], start: int, end: int
) -> list[dict[str, Any]]:
    """Emit plain text runs for joined[start:end], preserving per-segment annotations."""
    runs: list[dict[str, Any]] = []
    i = start
    while i < end:
        base = bases[i]
        j = i + 1
        while j < end and bases[j] is base:
            j += 1
        chunk = joined[i:j]
        if chunk:
            runs.append(_text_run(chunk, base))
        i = j
    return runs


def _emit_markup_run(
    kind: str,
    payload: dict[str, Any],
    base: dict[str, Any],
    counters: dict[str, int],
) -> dict[str, Any]:
    if kind == "input":
        width = int(payload["width"])
        placeholder = str(payload["placeholder"])
        signature = f"{width}\0{placeholder.casefold()}"
        counters["input"] = counters.get("input", 0) + 1
        key = field_key("input", signature, counters["input"])
        return {
            "type": "input",
            "key": key,
            "width": width,
            "placeholder": placeholder,
            "default": "",
        }
    if kind == "checkbox":
        default_raw = str(payload["default_raw"])
        default_bool = parse_checkbox_default(default_raw)
        signature = f"{default_bool}\0{default_raw.strip().casefold()}"
        counters["checkbox"] = counters.get("checkbox", 0) + 1
        key = field_key("checkbox", signature, counters["checkbox"])
        return {
            "type": "checkbox",
            "key": key,
            "default": "true" if default_bool else "false",
        }
    if kind == "nav_label":
        return {"type": "nav_label", "label": payload["label"]}
    if kind == "nav_goto":
        return _text_run(payload["text"], base, nav_goto=payload["label"])
    if kind == "nav_gotopage":
        return _text_run(payload["text"], base, nav_gotopage=payload["label"])
    return _text_run("", base)


def _split_joined_markup(
    joined: str, bases: list[dict[str, Any]], counters: dict[str, int]
) -> list[dict[str, Any]]:
    events: list[tuple[int, int, str, dict[str, Any]]] = []
    events.extend(_field_spans(joined))
    events.extend(iter_nav_tag_spans(joined))
    events.sort(key=lambda item: item[0])
    # Resolve overlaps: keep earlier span.
    filtered: list[tuple[int, int, str, dict[str, Any]]] = []
    cursor = 0
    for start, end, kind, payload in events:
        if start < cursor:
            continue
        filtered.append((start, end, kind, payload))
        cursor = end

    runs: list[dict[str, Any]] = []
    pos = 0
    for start, end, kind, payload in filtered:
        if start > pos:
            runs.extend(_plain_runs_from_joined(joined, bases, pos, start))
        base = bases[start] if 0 <= start < len(bases) else {}
        runs.append(_emit_markup_run(kind, payload, base, counters))
        pos = end
    if pos < len(joined):
        runs.extend(_plain_runs_from_joined(joined, bases, pos, len(joined)))
    return runs


def expand_rich_text(
    rich: list[dict[str, Any]] | None, counters: dict[str, int]
) -> list[dict[str, Any]]:
    """Expand field/nav tags. Join Notion rich_text parts first — tags often span runs."""
    if not rich:
        return []
    segments: list[tuple[str, dict[str, Any]]] = []
    for part in rich:
        text = str(part.get("text", ""))
        if text:
            segments.append((text, part))
    if not segments:
        return []

    joined = "".join(text for text, _ in segments)
    if not (_INPUT_TAG.search(joined) or _CB_TAG.search(joined) or has_nav_tags(joined)):
        return _merge_adjacent_text([_text_run(text, part) for text, part in segments])

    bases: list[dict[str, Any]] = []
    for text, part in segments:
        bases.extend([part] * len(text))
    return _merge_adjacent_text(_split_joined_markup(joined, bases, counters))


def _register_runs(runs: list[dict[str, Any]], specs: dict[str, FieldSpec]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for run in runs:
        kind = run.get("type")
        if kind == "text":
            item: dict[str, Any] = {
                "text": run.get("text", ""),
                "annotations": run.get("annotations") or {},
            }
            if run.get("link"):
                item["link"] = run["link"]
            cleaned.append(item)
        elif kind == "input":
            specs[str(run["key"])] = FieldSpec(
                key=str(run["key"]),
                kind="input",
                default="",
                width=int(run.get("width") or 10),
                placeholder=str(run.get("placeholder") or ""),
            )
        elif kind == "checkbox":
            specs[str(run["key"])] = FieldSpec(
                key=str(run["key"]),
                kind="checkbox",
                default=str(run.get("default") or "false"),
            )
        # nav_label intentionally omitted from rich_text
    return cleaned


def _cell_source_rich(cell: Any) -> list[dict[str, Any]]:
    if isinstance(cell, list):
        return cell
    if isinstance(cell, dict):
        rich = cell.get("rich_text")
        if isinstance(rich, list):
            return rich
    return []


def annotate_document_fields(
    document: list[dict[str, Any]],
    *,
    page_nav: dict[str, UUID] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, FieldSpec]]:
    """Annotate blocks with inline `runs`, resolve nav tags, collect field specs."""
    counters: dict[str, int] = {}
    specs: dict[str, FieldSpec] = {}
    output: list[dict[str, Any]] = []

    for raw in document:
        block = dict(raw)
        rich = block.get("rich_text")
        if isinstance(rich, list):
            runs = expand_rich_text(rich, counters)
            block["runs"] = runs
            block["rich_text"] = _register_runs(runs, specs)

        if block.get("type") == "table" and isinstance(block.get("rows"), list):
            new_rows: list[list[dict[str, Any]]] = []
            for row in block["rows"]:
                if not isinstance(row, list):
                    continue
                new_row: list[dict[str, Any]] = []
                for cell in row:
                    cell_runs = expand_rich_text(_cell_source_rich(cell), counters)
                    new_row.append(
                        {
                            "rich_text": _register_runs(cell_runs, specs),
                            "runs": cell_runs,
                        }
                    )
                new_rows.append(new_row)
            block["rows"] = new_rows
        output.append(block)

    resolve_nav_in_document(output, page_nav or {})
    return output, specs


def known_field_keys(document: list[dict[str, Any]]) -> set[str]:
    _, specs = annotate_document_fields(document)
    return set(specs)


def default_field_values(specs: dict[str, FieldSpec]) -> dict[str, str]:
    return {key: spec.default for key, spec in specs.items()}
