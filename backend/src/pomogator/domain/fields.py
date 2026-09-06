"""Pomogator Notion markup tags: interactive fields."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal

_INPUT_TAG = re.compile(
    r"\{pmg\.field\.input\(\{(\d+)\s*,\s*(.*?)\}\)\}",
    re.IGNORECASE | re.DOTALL,
)
_CB_TAG = re.compile(r"\{pmg\.field\.cb\(([^)]*)\)\}", re.IGNORECASE)
_FIELD_PATTERN = re.compile(
    r"\{pmg\.field\.input\(\{(\d+)\s*,\s*(.*?)\}\)\}|\{pmg\.field\.cb\(([^)]*)\)\}",
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


def _text_run(text: str, base: dict[str, Any]) -> dict[str, Any]:
    run: dict[str, Any] = {
        "type": "text",
        "text": text,
        "annotations": dict(base.get("annotations") or {}),
    }
    if base.get("link"):
        run["link"] = base["link"]
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
        ):
            prev["text"] = str(prev.get("text", "")) + str(run.get("text", ""))
        else:
            merged.append(dict(run))
    return merged


def _split_text_runs(
    text: str, base: dict[str, Any], counters: dict[str, int]
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    cursor = 0
    for match in _FIELD_PATTERN.finditer(text):
        if match.start() > cursor:
            chunk = text[cursor : match.start()]
            if chunk:
                runs.append(_text_run(chunk, base))
        if match.group(1) is not None:
            width = max(1, min(120, int(match.group(1))))
            placeholder = (match.group(2) or "").strip()
            signature = f"{width}\0{placeholder.casefold()}"
            counters["input"] = counters.get("input", 0) + 1
            key = field_key("input", signature, counters["input"])
            runs.append(
                {
                    "type": "input",
                    "key": key,
                    "width": width,
                    "placeholder": placeholder,
                    "default": "",
                }
            )
        else:
            default_raw = match.group(3) or ""
            default_bool = parse_checkbox_default(default_raw)
            signature = f"{default_bool}\0{default_raw.strip().casefold()}"
            counters["checkbox"] = counters.get("checkbox", 0) + 1
            key = field_key("checkbox", signature, counters["checkbox"])
            runs.append(
                {
                    "type": "checkbox",
                    "key": key,
                    "default": "true" if default_bool else "false",
                }
            )
        cursor = match.end()
    if cursor < len(text):
        chunk = text[cursor:]
        if chunk:
            runs.append(_text_run(chunk, base))
    return runs


def expand_rich_text(
    rich: list[dict[str, Any]] | None, counters: dict[str, int]
) -> list[dict[str, Any]]:
    if not rich:
        return []
    runs: list[dict[str, Any]] = []
    for part in rich:
        text = str(part.get("text", ""))
        if not text:
            continue
        if _INPUT_TAG.search(text) or _CB_TAG.search(text):
            runs.extend(_split_text_runs(text, part, counters))
        else:
            runs.append(_text_run(text, part))
    return _merge_adjacent_text(runs)


def _register_runs(runs: list[dict[str, Any]], specs: dict[str, FieldSpec]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for run in runs:
        kind = run.get("type")
        if kind == "text":
            cleaned.append(
                {
                    "text": run.get("text", ""),
                    "annotations": run.get("annotations") or {},
                    **({"link": run["link"]} if run.get("link") else {}),
                }
            )
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
) -> tuple[list[dict[str, Any]], dict[str, FieldSpec]]:
    """Annotate blocks with inline `runs` and collect field specs/defaults."""
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
    return output, specs


def known_field_keys(document: list[dict[str, Any]]) -> set[str]:
    _, specs = annotate_document_fields(document)
    return set(specs)


def default_field_values(specs: dict[str, FieldSpec]) -> dict[str, str]:
    return {key: spec.default for key, spec in specs.items()}
