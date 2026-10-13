from typing import Protocol

from pomogator.infrastructure.notion.client import ImportedCountry, PageSnapshot


class ContentImporter(Protocol):
    async def import_country(
        self,
        page_id: str,
        slug: str,
        fallback_flag: str,
        snapshots: dict[str, PageSnapshot] | None = None,
    ) -> ImportedCountry: ...
