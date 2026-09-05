from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pomogator.infrastructure.db.models import CountryModel, EntitlementModel, PageModel, UserModel


class ContentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def countries(self) -> list[CountryModel]:
        result = await self.session.scalars(
            select(CountryModel).where(CountryModel.enabled).order_by(CountryModel.title)
        )
        return list(result)

    async def country_by_slug(self, slug: str) -> CountryModel | None:
        result = await self.session.scalar(
            select(CountryModel).where(CountryModel.slug == slug, CountryModel.enabled)
        )
        return result

    async def page(self, page_id: UUID) -> PageModel | None:
        return await self.session.get(PageModel, page_id)

    async def root_page(self, country_id: UUID) -> PageModel | None:
        result = await self.session.scalar(
            select(PageModel).where(
                PageModel.country_id == country_id,
                PageModel.parent_id.is_(None),
                PageModel.archived.is_(False),
            )
        )
        return result

    async def children(self, country_id: UUID, parent_id: UUID | None) -> list[PageModel]:
        stmt = (
            select(PageModel)
            .where(
                PageModel.country_id == country_id,
                PageModel.parent_id == parent_id,
                PageModel.archived.is_(False),
            )
            .order_by(PageModel.position)
        )
        return list(await self.session.scalars(stmt))

    async def entitled(self, user_id: UUID, country_id: UUID) -> bool:
        return bool(
            await self.session.scalar(
                select(EntitlementModel.id).where(
                    EntitlementModel.user_id == user_id,
                    EntitlementModel.country_id == country_id,
                    EntitlementModel.active,
                )
            )
        )

    async def upsert_user(
        self, telegram_id: int, first_name: str, username: str | None
    ) -> UserModel:
        user = await self.session.scalar(
            select(UserModel).where(UserModel.telegram_id == telegram_id)
        )
        if user is None:
            user = UserModel(telegram_id=telegram_id, first_name=first_name, username=username)
            self.session.add(user)
        else:
            user.first_name, user.username = first_name, username
        await self.session.flush()
        return user
