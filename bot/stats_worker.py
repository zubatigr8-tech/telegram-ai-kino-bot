"""Bot profilida obunachilar sonini ko'rsatadi.

Telegram profildagi "monthly users" yozuvini o'zi hisoblaydi — uni bot o'zgartira olmaydi.
Shuning uchun sonni bot tavsiflariga yozamiz:
- short description — bot profilida, nomi ostida ko'rinadi (masalan "👥 12 345 obunachi • ...");
- description — botni birinchi marta ochganda, /start'dan oldin "Bot nima qila oladi?" oynasida.

Son o'zgargandagina yangilanadi (Telegram bu so'rovlarni cheklaydi)."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from sqlalchemy import func, select

from shared.config import settings
from shared.db.database import get_session
from shared.db.models import User

logger = logging.getLogger(__name__)

UPDATE_INTERVAL_SECONDS = 15 * 60
SHORT_DESCRIPTION_LIMIT = 120
DESCRIPTION_LIMIT = 512


def format_count(count: int) -> str:
    """12345 → "12 345" """
    return f"{count:,}".replace(",", " ")


async def count_subscribers() -> int:
    async with get_session() as session:
        return await session.scalar(select(func.count()).select_from(User).where(User.is_blocked.is_(False))) or 0


async def update_profile_stats(bot: Bot, last: dict) -> None:
    count = format_count(await count_subscribers())
    texts = {
        "short": settings.BOT_SHORT_DESCRIPTION.replace("{count}", count)[:SHORT_DESCRIPTION_LIMIT],
        "full": settings.BOT_DESCRIPTION.replace("{count}", count)[:DESCRIPTION_LIMIT],
    }
    if texts["short"] != last.get("short"):
        await bot.set_my_short_description(short_description=texts["short"])
        last["short"] = texts["short"]
        logger.info("Bot profili yangilandi: %s", texts["short"])
    if texts["full"] != last.get("full"):
        await bot.set_my_description(description=texts["full"])
        last["full"] = texts["full"]


async def run_stats_worker(bot: Bot) -> None:
    if not settings.SHOW_SUBSCRIBER_COUNT:
        return
    last: dict = {}
    while True:
        try:
            await update_profile_stats(bot, last)
        except asyncio.CancelledError:
            raise
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            continue
        except Exception:
            logger.exception("Bot profilidagi obunachilar sonini yangilab bo'lmadi")
        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)
