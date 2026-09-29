import asyncio
import logging
import socket

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError
from aiogram.types import ErrorEvent

from bot.backup_worker import run_backup_worker
from bot.broadcast_worker import run_broadcast_worker
from bot.handlers import admin_panel, admin_tools, fallback, join_requests, media, music, start
from bot.middlewares import SubscriptionMiddleware, UserMiddleware
from shared.config import settings
from shared.db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


class RetryMiddleware(BaseRequestMiddleware):
    """Internet vaqtincha uzilsa (Windows'da "semaphore timeout" kabi), so'rovni 3 martagacha qaytaradi."""

    async def __call__(self, make_request, bot, method):
        for attempt in range(3):
            try:
                return await make_request(bot, method)
            except TelegramNetworkError as exc:
                if attempt == 2:
                    raise
                logger.warning("Telegram'ga ulanishda uzilish (%s), qayta urinilmoqda...", exc)
                await asyncio.sleep(2)


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida topilmadi. @BotFather'dan olib, .env ga qo'shing.")

    await init_db()

    # 300 soniya: katta videoni sekin internetda yuklash standart 60 soniyaga sig'masligi mumkin
    proxy = getattr(settings, "PROXY_URL", "") or None
    session = AiohttpSession(proxy=proxy, timeout=300)
    if proxy is None:
        # Ba'zi tarmoqlarda IPv6 ishlamaydi va ulanish uzoq kutib uziladi — faqat IPv4 ishlatamiz
        session._connector_init["family"] = socket.AF_INET
    session.middleware(RetryMiddleware())
    bot = Bot(token=settings.BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
    # adminning /admin oqimi oddiy foydalanuvchi handlerlariga tushib qoladi.
    dp.include_router(admin_panel.router)
    dp.include_router(admin_tools.router)
    dp.include_router(start.router)
    dp.include_router(media.router)  # Instagram / YouTube / TikTok havolalari
    dp.include_router(music.router)  # qo'shiq nomi yoki matni bo'yicha qidirish
    dp.include_router(join_requests.router)  # kanalga qo'shilish so'rovlarini tasdiqlash
    dp.include_router(fallback.router)  # oxirgi bo'lishi kerak: qolgan barcha xabarlar uchun yo'riqnoma

    # Telegram serveriga ulanishni tekshiramiz: ulanib bo'lmasa, bot jimgina osilib qolmasin
    logger.info("Telegram serveriga ulanilmoqda (api.telegram.org)...")
    try:
        me = await asyncio.wait_for(bot.me(), timeout=30)
        # Token boshqa joyda webhook bilan ishlatilgan bo'lsa, polling xabarlarni olmaydi — o'chirib qo'yamiz
        await asyncio.wait_for(bot.delete_webhook(drop_pending_updates=False), timeout=30)
    except (asyncio.TimeoutError, TelegramNetworkError) as exc:
        await bot.session.close()
        raise SystemExit(
            f"\n❌ Telegram serveriga (api.telegram.org) ulanib bo'lmadi: {type(exc).__name__}\n"
            "   Internetingiz Telegram API'ni to'sayotgan bo'lishi mumkin.\n"
            "   Yechim: kompyuterda VPN yoqing yoki .env faylida PROXY_URL ni ko'rsating, so'ng botni qayta ishga tushiring."
        )
    except TelegramUnauthorizedError:
        await bot.session.close()
        raise SystemExit("\n❌ BOT_TOKEN noto'g'ri yoki bekor qilingan. @BotFather → /mybots → API Token'dan yangisini oling.")
    logger.info("✅ Bot ishga tushdi: @%s — Telegram'da aynan shu botga yozing", me.username)
    workers = [
        asyncio.create_task(run_broadcast_worker(bot)),
        asyncio.create_task(run_backup_worker()),
    ]
    try:
        await dp.start_polling(bot)
    finally:
        # Polling to'xtaganda (Ctrl+C yoki hosting SIGTERM yuborganda) fon vazifalarini ham
        # to'xtatamiz, aks holda jarayon yopilmay osilib qoladi
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
