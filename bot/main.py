import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.backup_worker import run_backup_worker
from bot.broadcast_worker import run_broadcast_worker
from bot.handlers import admin_panel, admin_tools, channel_owner, movie, start, user
from bot.middlewares import SubscriptionMiddleware, UserMiddleware
from shared.config import settings
from bot.services import load_admins
from shared.db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida topilmadi. @BotFather'dan olib, .env ga qo'shing.")

    await init_db()
    await load_admins()

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Outer — handler topilmasa ham ishlaydi (foydalanuvchini ro'yxatga olish, blok tekshiruvi)
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        # Masalan internet vaqtincha uzilib, Telegram callback "eskirib qolgan"
        # holatlarda butun jarayonni to'xtatmasdan, faqat qisqa xabar bilan davom etamiz.
        logger.error("Handlerda xatolik: %s", event.exception, exc_info=event.exception)
        return True

    # Tartib muhim: admin_panel va admin_tools birinchi bo'lishi kerak, aks holda
    # adminning /admin oqimi yoki video/fayllari oddiy foydalanuvchi handlerlariga tushib qoladi.
    dp.include_router(admin_panel.menu)  # menyu tugmalari jarayonlardan oldin tekshiriladi
    dp.include_router(admin_panel.router)
    dp.include_router(admin_tools.router)
    dp.include_router(start.router)
    dp.include_router(channel_owner.router)  # kanal admini: /kanal, "Hammasini tasdiqlash"
    dp.include_router(user.router)  # Shorts, Premium, kanal zayavkalari
    dp.include_router(movie.router)  # oxirgi bo'lishi kerak: unda qolgan barcha xabarlar uchun yo'riqnoma bor

    logger.info("Bot ishga tushdi...")
    workers = [
        asyncio.create_task(run_broadcast_worker(bot)),
        asyncio.create_task(run_backup_worker()),
    ]
    try:
        # chat_join_request (kanal zayavkalari) ham kelishi uchun ishlatilayotgan update turlarini aniq beramiz
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Polling to'xtaganda (Ctrl+C yoki hosting SIGTERM yuborganda) fon vazifalarini ham
        # to'xtatamiz, aks holda jarayon yopilmay osilib qoladi
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
