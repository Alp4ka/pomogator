import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class AccessLevel(StrEnum):
    FREE = "free"
    PAID = "paid"


_ACCESS_TAG = re.compile(r"\{pmg\.access\.(pay|free)\}", re.IGNORECASE)
_NAV_PAGE_TAG = re.compile(r"\{pmg\.nav\.page\(([^)]*)\)\}", re.IGNORECASE)
_LABEL_CHARS = re.compile(r"^[\w.\-]+$", re.UNICODE)


def normalize_nav_label(raw: str) -> str | None:
    label = raw.strip()
    if not label or len(label) > 64:
        return None
    if not _LABEL_CHARS.fullmatch(label):
        return None
    return label


def parse_page_title(
    title: str, inherited: AccessLevel = AccessLevel.FREE
) -> tuple[str, AccessLevel, str | None]:
    """Strip access/nav title tags; return clean title, access level, optional page nav label."""
    level = inherited
    for match in _ACCESS_TAG.finditer(title):
        level = AccessLevel.PAID if match.group(1).lower() == "pay" else AccessLevel.FREE
    nav_label: str | None = None
    for match in _NAV_PAGE_TAG.finditer(title):
        candidate = normalize_nav_label(match.group(1))
        if candidate:
            nav_label = candidate
    clean = _NAV_PAGE_TAG.sub(" ", _ACCESS_TAG.sub(" ", title))
    return " ".join(clean.split()), level, nav_label


def parse_access_title(
    title: str, inherited: AccessLevel = AccessLevel.FREE
) -> tuple[str, AccessLevel]:
    clean, level, _nav = parse_page_title(title, inherited)
    return clean, level


@dataclass(frozen=True, slots=True)
class Country:
    id: UUID
    notion_page_id: str
    slug: str
    title: str
    flag: str


@dataclass(frozen=True, slots=True)
class ContentPage:
    id: UUID
    country_id: UUID
    parent_id: UUID | None
    notion_page_id: str
    title: str
    access_level: AccessLevel
    document: list[dict[str, Any]]
