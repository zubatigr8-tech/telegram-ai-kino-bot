import asyncio
import logging
import shutil

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from video_enhancer_bot import handlers
from video_enhancer_bot.config import settings
from video_enhancer_bot.engines import get_engine
from video_enhancer_bot.jobs import JobQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida topilmadi. @BotFather'dan olib, .env ga qo'shing.")
    for binary in (settings.FFMPEG_BIN, settings.FFPROBE_BIN):
        if shutil.which(binary) is None:
            raise RuntimeError(f"{binary} topilmadi. ffmpeg'ni o'rnating (README'ga qarang).")

    session = None
    if settings.TELEGRAM_API_URL:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(settings.TELEGRAM_API_URL, is_local=settings.TELEGRAM_API_LOCAL),
            timeout=600,  # katta fayllarni yuborish uzoq davom etishi mumkin
        )
    bot = Bot(token=settings.BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    engine = get_engine()
    jobs = JobQueue(bot, engine)
    dp["jobs"] = jobs  # handlerlarga `jobs` argumenti sifatida uzatiladi

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.error("Handlerda xatolik: %s", event.exception, exc_info=event.exception)
        return True

    dp.include_router(handlers.router)
    await bot.set_my_commands([BotCommand(command="start", description="Botni ishga tushirish")])

    jobs.start()
    logger.info("Video sifatini oshiruvchi bot ishga tushdi (engine=%s)", engine.name)
    try:
        await dp.start_polling(bot)
    finally:
        await jobs.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
