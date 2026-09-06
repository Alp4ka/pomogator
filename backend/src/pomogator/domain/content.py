import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class AccessLevel(StrEnum):
    FREE = "free"
    PAID = "paid"


_ACCESS_TAG = re.compile(r"\{pmg\.access\.(pay|free)\}", re.IGNORECASE)


def parse_access_title(
    title: str, inherited: AccessLevel = AccessLevel.FREE
) -> tuple[str, AccessLevel]:
    level = inherited
    for match in _ACCESS_TAG.finditer(title):
        level = AccessLevel.PAID if match.group(1).lower() == "pay" else AccessLevel.FREE
    clean = _ACCESS_TAG.sub(" ", title)
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
