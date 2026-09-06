from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from pomogator.config import CountrySource
from pomogator.domain.links import remap_internal_links
from pomogator.infrastructure.db.models import (
    CountryModel,
    ImageModel,
    PageImageModel,
    PageModel,
    SyncRunModel,
)
from pomogator.infrastructure.notion.client import ImportedPage, NotionClient


class SyncCountry:
    def __init__(self, session: AsyncSession, notion: NotionClient):
        self.session, self.notion = session, notion

    async def __call__(self, source: CountrySource) -> None:
        country = await self.session.scalar(
            select(CountryModel).where(
                CountryModel.notion_page_id == source.page_id.replace("-", "")
            )
        )
        if country is None:
            country = CountryModel(
                notion_page_id=source.page_id.replace("-", ""),
                slug=source.slug,
                title=source.slug.title(),
                flag=source.flag,
            )
            self.session.add(country)
            await self.session.flush()
        run = SyncRunModel(country_id=country.id, status="running")
        self.session.add(run)
        await self.session.commit()
        run_id = run.id
        try:
            imported = await self.notion.import_country(source.page_id, source.slug, source.flag)
            await self.session.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"country-sync:{source.page_id}"},
            )
            await self.session.refresh(country)
            country.title, country.flag = imported.root.title, imported.flag
            await self.session.execute(
                update(PageModel).where(PageModel.country_id == country.id).values(archived=True)
            )
            page_ids = select(PageModel.id).where(PageModel.country_id == country.id)
            await self.session.execute(
                delete(PageImageModel).where(PageImageModel.page_id.in_(page_ids))
            )
            known: dict[str, UUID] = {}

            async def save(node: ImportedPage, parent: UUID | None, position: int) -> None:
                page = await self.session.scalar(
                    select(PageModel).where(
                        PageModel.country_id == country.id,
                        PageModel.notion_page_id == node.notion_page_id,
                    )
                )
                if page is None:
                    page = PageModel(
                        country_id=country.id,
                        notion_page_id=node.notion_page_id,
                        parent_id=parent,
                        title=node.title,
                        access_level=node.access_level,
                        document=node.document,
                        position=position,
                        archived=False,
                    )
                    self.session.add(page)
                    await self.session.flush()
                else:
                    (
                        page.parent_id,
                        page.title,
                        page.access_level,
                        page.document,
                        page.position,
                        page.archived,
                    ) = parent, node.title, node.access_level, node.document, position, False
                known[node.notion_page_id] = page.id
                for index, child in enumerate(node.children):
                    await save(child, page.id, index)

            await save(imported.root, None, 0)
            for image in imported.images:
                stored = await self.session.scalar(
                    select(ImageModel).where(ImageModel.sha256 == image.sha256)
                )
                if stored is None:
                    stored = ImageModel(
                        sha256=image.sha256,
                        mime_type=image.mime_type,
                        data=image.data,
                        byte_size=len(image.data),
                    )
                    self.session.add(stored)
            await self.session.flush()
            for page in await self.session.scalars(
                select(PageModel).where(
                    PageModel.country_id == country.id, PageModel.archived.is_(False)
                )
            ):
                linked: set[UUID] = set()
                for block in page.document:
                    if digest := block.get("image_id"):
                        image_id = await self.session.scalar(
                            select(ImageModel.id).where(ImageModel.sha256 == digest)
                        )
                        if image_id and image_id not in linked:
                            self.session.add(PageImageModel(page_id=page.id, image_id=image_id))
                            linked.add(image_id)
            for page in await self.session.scalars(
                select(PageModel).where(PageModel.country_id == country.id)
            ):
                page.document = remap_internal_links(list(page.document), known)
                flag_modified(page, "document")
            country.content_version += 1
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            failed_run = await self.session.get(SyncRunModel, run_id)
            if failed_run is None:
                raise RuntimeError("Sync run disappeared") from exc
            run = failed_run
            run.status = "failed"
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(UTC)
            await self.session.commit()
            raise
