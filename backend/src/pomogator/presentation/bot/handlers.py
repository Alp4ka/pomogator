from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from celery import Celery
from sqlalchemy import select

from pomogator.config import get_settings
from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.db.models import CountryModel, PageModel, UserModel

router = Router()
PAGE_SIZE = 8


async def keyboard(page: int = 0) -> InlineKeyboardMarkup:
    async with SessionFactory() as session:
        countries = list(
            await session.scalars(
                select(CountryModel).where(CountryModel.enabled).order_by(CountryModel.title)
            )
        )
    start, chunk = page * PAGE_SIZE, countries[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    rows = [
        [InlineKeyboardButton(text=f"{c.flag} {c.title}", callback_data=f"country:{c.slug}")]
        for c in chunk
    ]
    nav = []
    if page:
        nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"page:{page - 1}"))
    if start + PAGE_SIZE < len(countries):
        nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def start(message: Message) -> None:
    if message.from_user:
        async with SessionFactory() as session:
            user = await session.scalar(
                select(UserModel).where(UserModel.telegram_id == message.from_user.id)
            )
            if user is None:
                session.add(
                    UserModel(
                        telegram_id=message.from_user.id,
                        first_name=message.from_user.first_name,
                        username=message.from_user.username,
                    )
                )
            else:
                user.first_name = message.from_user.first_name
                user.username = message.from_user.username
            await session.commit()
    await message.answer(
        "<b>Помогатор по переезду</b>\n\n"
        "Выберите страну — покажем инструкции, документы и полезные контакты.",
        reply_markup=await keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("sync"))
async def sync_content(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id not in get_settings().admin_telegram_ids:
        await message.answer("Команда доступна только администратору.")
        return
    Celery(broker=get_settings().redis_url).send_task("pomogator.sync_all")
    await message.answer(
        "<b>Синхронизация запущена.</b> Результат появится после обработки Notion.",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("page:"))
async def paginate(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or query.data is None:
        await query.answer()
        return
    await query.message.edit_reply_markup(
        reply_markup=await keyboard(int(query.data.split(":")[1]))
    )
    await query.answer()


@router.callback_query(F.data.startswith("country:"))
async def open_country(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or query.data is None:
        await query.answer()
        return
    slug = query.data.split(":", 1)[1]
    async with SessionFactory() as session:
        country = await session.scalar(select(CountryModel).where(CountryModel.slug == slug))
        has_content = country is not None and bool(
            await session.scalar(
                select(PageModel.id).where(PageModel.country_id == country.id).limit(1)
            )
        )
    if not has_content:
        Celery(broker=get_settings().redis_url).send_task("pomogator.sync_country", args=[slug])
        await query.message.answer(
            "⏳ <b>Готовим путеводитель</b>\n"
            "Материалы загружаются из Notion. Попробуйте открыть страну через минуту.",
            parse_mode="HTML",
        )
        await query.answer()
        return
    url = f"{get_settings().telegram_webapp_url}?country={slug}"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть путеводитель", web_app=WebAppInfo(url=url))]
        ]
    )
    await query.message.answer(
        "Путеводитель откроется в защищённом приложении Telegram.", reply_markup=markup
    )
    await query.answer()


def dispatcher() -> Dispatcher:
    value = Dispatcher()
    value.include_router(router)
    return value
