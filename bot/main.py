import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from bot.backup_worker import run_backup_worker
from bot.broadcast_worker import run_broadcast_worker
from bot.handlers import admin_panel, admin_tools, ai_chat, files, movie, start
from bot.middlewares import SubscriptionMiddleware
from shared.config import settings
from shared.db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida topilmadi. @BotFather'dan olib, .env ga qo'shing.")

    await init_db()

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        # Masalan internet vaqtincha uzilib, Telegram callback "eskirib qolgan"
        # holatlarda butun jarayonni to'xtatmasdan, faqat qisqa xabar bilan davom etamiz.
        logger.error("Handlerda xatolik: %s", event.exception)
        return True

    # Tartib muhim: admin_panel va admin_tools birinchi bo'lishi kerak, aks holda
    # adminning /admin oqimi yoki video/fayllari oddiy foydalanuvchi handlerlariga tushib qoladi.
    dp.include_router(admin_panel.router)
    dp.include_router(admin_tools.router)
    dp.include_router(start.router)
    dp.include_router(movie.router)
    dp.include_router(ai_chat.router)
    dp.include_router(files.router)  # rasm/hujjatlar — F.text bo'lmagani uchun ai_chat'dan keyin ham xavfsiz

    logger.info("Bot ishga tushdi...")
    await asyncio.gather(
        dp.start_polling(bot),
        run_broadcast_worker(bot),
        run_backup_worker(),
    )


if __name__ == "__main__":
    asyncio.run(main())
