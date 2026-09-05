import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class AccessLevel(StrEnum):
    FREE = "free"
    PAID = "paid"


_TAG = re.compile(r"(?:^|\s)\[(Бесплатно|Платным)\](?=\s|$)", re.IGNORECASE)


def parse_access_title(
    title: str, inherited: AccessLevel = AccessLevel.FREE
) -> tuple[str, AccessLevel]:
    level = inherited
    for match in _TAG.finditer(title):
        level = AccessLevel.FREE if match.group(1).lower() == "бесплатно" else AccessLevel.PAID
    clean = _TAG.sub(" ", title)
    return " ".join(clean.split()), level


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
