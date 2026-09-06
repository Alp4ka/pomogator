from aiogram import Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from celery import Celery
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pomogator.application.payments import (
    PurchaseError,
    purchase_country_access,
    user_has_country_access,
)
from pomogator.application.sync_waiters import register_sync_waiter
from pomogator.config import get_settings
from pomogator.infrastructure.db.base import SessionFactory
from pomogator.infrastructure.db.models import CountryModel, PageModel, UserModel
from pomogator.infrastructure.telegram.notify import country_ready_keyboard

router = Router()
PAGE_SIZE = 8

MENU_COUNTRIES = "🌍 Страны"
MENU_ACCESS = "✦ Полный доступ"
MENU_HELP = "❓ Помощь"

BOT_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="countries", description="Список стран"),
    BotCommand(command="access", description="Полный доступ"),
    BotCommand(command="help", description="Как пользоваться"),
]


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MENU_COUNTRIES)],
            [KeyboardButton(text=MENU_ACCESS), KeyboardButton(text=MENU_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие в меню",
    )


def webapp_url(slug: str) -> str:
    return f"{get_settings().telegram_webapp_url}?country={slug}"


async def country_keyboard(page: int = 0) -> InlineKeyboardMarkup:
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
    nav: list[InlineKeyboardButton] = []
    if page:
        nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"page:{page - 1}"))
    if start + PAGE_SIZE < len(countries):
        nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"page:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def buy_keyboard(telegram_id: int, page: int = 0) -> InlineKeyboardMarkup:
    async with SessionFactory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        countries = list(
            await session.scalars(
                select(CountryModel).where(CountryModel.enabled).order_by(CountryModel.title)
            )
        )
        rows: list[list[InlineKeyboardButton]] = []
        start = page * PAGE_SIZE
        chunk = countries[start : start + PAGE_SIZE]
        for country in chunk:
            owned = False
            if user is not None:
                owned = await user_has_country_access(
                    session, user_id=user.id, country_id=country.id
                )
            if owned:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=f"✓ {country.flag} {country.title} · открыть",
                            web_app=WebAppInfo(url=webapp_url(country.slug)),
                        )
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=f"✦ {country.flag} {country.title} · 0 ₽",
                            callback_data=f"buy:{country.slug}",
                        )
                    ]
                )
        nav: list[InlineKeyboardButton] = []
        if page:
            nav.append(InlineKeyboardButton(text="‹ Назад", callback_data=f"buypage:{page - 1}"))
        if start + PAGE_SIZE < len(countries):
            nav.append(InlineKeyboardButton(text="Далее ›", callback_data=f"buypage:{page + 1}"))
        if nav:
            rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def upsert_user_from_telegram(
    telegram_id: int, first_name: str | None, username: str | None
) -> UserModel:
    name = first_name or ""
    async with SessionFactory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.telegram_id == telegram_id))
        if user is None:
            user = UserModel(telegram_id=telegram_id, first_name=name, username=username)
            session.add(user)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                user = await session.scalar(
                    select(UserModel).where(UserModel.telegram_id == telegram_id)
                )
                if user is None:
                    raise
                user.first_name = name
                user.username = username
                await session.commit()
            await session.refresh(user)
            return user
        user.first_name = name
        user.username = username
        await session.commit()
        await session.refresh(user)
        return user


async def upsert_user(message: Message) -> UserModel | None:
    if not message.from_user:
        return None
    return await upsert_user_from_telegram(
        message.from_user.id, message.from_user.first_name, message.from_user.username
    )


async def send_countries(message: Message) -> None:
    await message.answer(
        "<b>Выберите страну</b>\nОткроем путеводитель в защищённом приложении Telegram.",
        reply_markup=await country_keyboard(),
        parse_mode="HTML",
    )


async def send_help(message: Message) -> None:
    await message.answer(
        "<b>Как пользоваться Помогатором</b>\n\n"
        f"1. «{MENU_COUNTRIES}» — выбрать страну и открыть путеводитель.\n"
        f"2. «{MENU_ACCESS}» — купить полный доступ прямо в боте (выбор страны → подтверждение).\n"
        "3. Бесплатные материалы доступны сразу; закрытые этапы — после оплаты.\n\n"
        "Меню внизу всегда под рукой.",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def send_access_menu(message: Message) -> None:
    await upsert_user(message)
    if not message.from_user:
        return
    await message.answer(
        "<b>Полный доступ</b>\n\n"
        "1. Выберите страну ниже.\n"
        "2. Подтвердите оплату (сейчас тестовая — <b>0 ₽</b>).\n"
        "3. Сразу откройте путеводитель с разблокированными материалами.\n\n"
        "Доступ привязан к вашему Telegram-аккаунту.",
        reply_markup=await buy_keyboard(message.from_user.id),
        parse_mode="HTML",
    )


@router.message(CommandStart())
async def start(message: Message) -> None:
    await upsert_user(message)
    await message.answer(
        "<b>Помогатор по переезду</b>\n\n"
        "Выберите страну — покажем инструкции, документы и полезные контакты.\n"
        "Меню внизу: страны, полный доступ и помощь.",
        reply_markup=main_menu(),
        parse_mode="HTML",
    )
    await send_countries(message)


@router.message(Command("countries"))
@router.message(F.text == MENU_COUNTRIES)
async def countries_menu(message: Message) -> None:
    await send_countries(message)


@router.message(Command("help"))
@router.message(F.text == MENU_HELP)
async def help_menu(message: Message) -> None:
    await send_help(message)


@router.message(Command("access"))
@router.message(F.text == MENU_ACCESS)
async def access_menu(message: Message) -> None:
    await send_access_menu(message)


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
        reply_markup=await country_keyboard(int(query.data.split(":")[1]))
    )
    await query.answer()


@router.callback_query(F.data.startswith("buypage:"))
async def buy_paginate(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or query.data is None or not query.from_user:
        await query.answer()
        return
    page = int(query.data.split(":")[1])
    await query.message.edit_reply_markup(reply_markup=await buy_keyboard(query.from_user.id, page))
    await query.answer()


@router.callback_query(F.data.startswith("buy:"))
async def buy_select(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or query.data is None or not query.from_user:
        await query.answer()
        return
    slug = query.data.split(":", 1)[1]
    async with SessionFactory() as session:
        country = await session.scalar(select(CountryModel).where(CountryModel.slug == slug))
        if country is None:
            await query.answer("Страна не найдена", show_alert=True)
            return
        user = await session.scalar(
            select(UserModel).where(UserModel.telegram_id == query.from_user.id)
        )
        if user is not None and await user_has_country_access(
            session, user_id=user.id, country_id=country.id
        ):
            await query.message.answer(
                f"✓ У вас уже есть полный доступ к <b>{country.flag} {country.title}</b>.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Открыть путеводитель",
                                web_app=WebAppInfo(url=webapp_url(country.slug)),
                            )
                        ]
                    ]
                ),
            )
            await query.answer()
            return
        title = f"{country.flag} {country.title}"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить оплату · 0 ₽", callback_data=f"buyok:{slug}")],
            [InlineKeyboardButton(text="Выбрать другую страну", callback_data="buyagain")],
        ]
    )
    await query.message.answer(
        f"<b>Полный доступ · {title}</b>\n\n"
        "Откроются закрытые этапы, контакты и обновления по этой стране.\n\n"
        "<b>Сейчас тестовая оплата — 0 ₽</b>, деньги не списываются.\n"
        "Нажмите «Подтвердить», чтобы выдать доступ.",
        reply_markup=markup,
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data == "buyagain")
async def buy_again(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or not query.from_user:
        await query.answer()
        return
    await query.message.answer(
        "<b>Выберите страну для полного доступа</b>",
        reply_markup=await buy_keyboard(query.from_user.id),
        parse_mode="HTML",
    )
    await query.answer()


@router.callback_query(F.data.startswith("buyok:"))
async def buy_confirm(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message) or query.data is None or not query.from_user:
        await query.answer()
        return
    slug = query.data.split(":", 1)[1]
    user = await upsert_user_from_telegram(
        query.from_user.id, query.from_user.first_name, query.from_user.username
    )
    async with SessionFactory() as session:
        country = await session.scalar(select(CountryModel).where(CountryModel.slug == slug))
        if country is None:
            await query.answer("Страна не найдена", show_alert=True)
            return
        title = f"{country.flag} {country.title}"
        url = webapp_url(country.slug)
        db_user = await session.scalar(select(UserModel).where(UserModel.id == user.id))
        if db_user is None:
            await query.answer("Пользователь не найден", show_alert=True)
            return
        if await user_has_country_access(session, user_id=db_user.id, country_id=country.id):
            await query.message.answer(
                f"✓ Доступ к <b>{title}</b> уже активен.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Открыть путеводитель", web_app=WebAppInfo(url=url)
                            )
                        ]
                    ]
                ),
            )
            await query.answer()
            return
        try:
            await purchase_country_access(
                session,
                user=db_user,
                country=country,
                idempotency_key=f"bot:{db_user.id}:{country.id}",
            )
        except PurchaseError as exc:
            await query.answer(str(exc), show_alert=True)
            return
    await query.message.answer(
        f"✅ <b>Полный доступ открыт</b>\n\n{title} — закрытые материалы доступны в Mini App.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Открыть путеводитель", web_app=WebAppInfo(url=url))]
            ]
        ),
    )
    await query.answer("Доступ выдан")


@router.callback_query(F.data == "showcountries")
async def show_countries(query: CallbackQuery) -> None:
    if not isinstance(query.message, Message):
        await query.answer()
        return
    await query.message.answer(
        "<b>Выберите страну</b>\nОткроем путеводитель в защищённом приложении Telegram.",
        reply_markup=await country_keyboard(),
        parse_mode="HTML",
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
        if query.from_user:
            register_sync_waiter(slug, query.from_user.id)
        Celery(broker=get_settings().redis_url).send_task("pomogator.sync_country", args=[slug])
        await query.message.answer(
            "⏳ <b>Готовим путеводитель</b>\n"
            "Материалы загружаются из Notion.\n"
            "Как только страница будет готова — пришлём сообщение с меню следующих шагов.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        await query.answer()
        return
    title = f"{country.flag} {country.title}" if country else slug
    await query.message.answer(
        f"<b>{title}</b>\nПутеводитель готов. Выберите следующий шаг:",
        reply_markup=country_ready_keyboard(slug),
        parse_mode="HTML",
    )
    await query.answer()


def dispatcher() -> Dispatcher:
    value = Dispatcher()
    value.include_router(router)
    return value
