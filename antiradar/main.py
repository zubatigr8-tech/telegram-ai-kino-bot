"""Antiradar botni ishga tushirish:  python -m antiradar.main"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from antiradar.config import settings
from antiradar.db import init_db
from antiradar.handlers import admin, location, settings as settings_handlers, start, subscription
from antiradar.middlewares import UserMiddleware
from antiradar.osm_import import run_osm_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("ANTIRADAR_BOT_TOKEN .env faylida topilmadi. @BotFather'dan olib, .env ga qo'shing.")

    await init_db()

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    middleware = UserMiddleware()
    dp.message.outer_middleware(middleware)
    dp.edited_message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)
    dp.pre_checkout_query.outer_middleware(middleware)

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.error("Handlerda xatolik: %s", event.exception, exc_info=event.exception)
        return True

    # Tartib muhim: admin birinchi (admin yuborgan oddiy joylashuv — kamera qo'shish),
    # location oxirgi (unda qolgan barcha xabarlar uchun javob bor).
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(location.router)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start / til"),
            BotCommand(command="subscribe", description="⭐ Obuna"),
            BotCommand(command="settings", description="⚙️ Sozlamalar"),
            BotCommand(command="help", description="❓ Yordam"),
        ]
    )

    logger.info("AI Antiradar bot ishga tushdi...")
    workers = [
        asyncio.create_task(location.warm_voice_cache()),
        # Radar va belgilar bazasini OSM'dan avtomatik yangilab turadi, keyin yangi iboralarni tayyorlaydi
        asyncio.create_task(run_osm_worker(on_updated=location.warm_voice_cache)),
    ]
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
