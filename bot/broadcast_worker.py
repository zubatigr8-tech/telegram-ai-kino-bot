"""Admin panelda yaratilgan xabarlarni fon rejimida barcha foydalanuvchilarga yuboradi."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select

from shared.db.database import get_session
from shared.db.models import BroadcastJob, User

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
DELAY_BETWEEN_MESSAGES = 0.05  # flood limitga tushmaslik uchun


async def _send_one(bot: Bot, user_id: int, job: BroadcastJob) -> bool:
    try:
        if job.photo_file_id:
            await bot.send_photo(user_id, job.photo_file_id, caption=job.text)
        else:
            await bot.send_message(user_id, job.text)
        return True
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        return await _send_one(bot, user_id, job)
    except TelegramForbiddenError:
        return False  # foydalanuvchi botni bloklagan
    except Exception:
        logger.exception("Xabar yuborilmadi: user_id=%s", user_id)
        return False


async def _process_pending_jobs(bot: Bot) -> None:
    async with get_session() as session:
        result = await session.execute(select(BroadcastJob).where(BroadcastJob.status == "pending"))
        jobs = list(result.scalars().all())
        if not jobs:
            return

        users_result = await session.execute(select(User.tg_id).where(User.is_blocked == False))  # noqa: E712
        user_ids = [row[0] for row in users_result.all()]

        for job in jobs:
            sent = 0
            for uid in user_ids:
                if await _send_one(bot, uid, job):
                    sent += 1
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
            job.sent_count = sent
            job.status = "done"
        await session.commit()


async def run_broadcast_worker(bot: Bot) -> None:
    while True:
        try:
            await _process_pending_jobs(bot)
        except Exception:
            logger.exception("Broadcast worker'da xatolik")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
