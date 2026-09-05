"""Telegram long-polling process."""

import asyncio
import logging

from aiogram import Bot

from pomogator.config import get_settings
from pomogator.presentation.bot.handlers import dispatcher


async def run() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for long polling")

    bot = Bot(settings.telegram_bot_token)
    dp = dispatcher()
    try:
        # Telegram does not allow webhook and long polling for one token at the same time.
        await bot.delete_webhook(drop_pending_updates=False)
        me = await bot.get_me()
        logging.getLogger(__name__).info("Long polling started for @%s", me.username)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
