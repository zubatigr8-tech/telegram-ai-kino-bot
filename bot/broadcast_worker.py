"""Admin panelda yaratilgan xabarlarni fon rejimida barcha foydalanuvchilarga yuboradi."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select, update

from shared.db.database import get_session
from shared.db.models import BroadcastJob, Channel, User

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
DELAY_BETWEEN_MESSAGES = 0.05  # flood limitga tushmaslik uchun
PROGRESS_SAVE_EVERY = 50  # har N ta yuborilgan xabardan keyin natija bazaga yoziladi
MAX_RETRIES = 3


async def _send(bot: Bot, user_id: int, job: BroadcastJob, parse_mode) -> None:
    if job.copy_message_id:
        # Botda yuborilgan xabarning aynan nusxasi (matn, rasm, video, tugmalar bilan)
        await bot.copy_message(user_id, job.copy_from_chat_id, job.copy_message_id)
    elif job.photo_file_id:
        # Rasm izohi (caption) 1024 belgidan oshmasligi kerak
        await bot.send_photo(user_id, job.photo_file_id, caption=job.text[:1024], parse_mode=parse_mode)
    else:
        await bot.send_message(user_id, job.text, parse_mode=parse_mode)


async def _send_one(bot: Bot, user_id: int, job: BroadcastJob) -> bool:
    parse_mode = "HTML"
    for _ in range(MAX_RETRIES):
        try:
            await _send(bot, user_id, job, parse_mode)
            return True
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramForbiddenError:
            return False  # foydalanuvchi botni bloklagan
        except TelegramBadRequest as exc:
            # Matnda "<" yoki noto'g'ri HTML bo'lsa — oddiy matn sifatida qayta yuboramiz
            if parse_mode is not None and "parse entities" in str(exc):
                parse_mode = None
                continue
            logger.warning("Xabar yuborilmadi: user_id=%s: %s", user_id, exc)
            return False
        except Exception:
            logger.exception("Xabar yuborilmadi: user_id=%s", user_id)
            return False
    return False


async def _set_job(job_id: int, **values) -> None:
    async with get_session() as session:
        await session.execute(update(BroadcastJob).where(BroadcastJob.id == job_id).values(**values))
        await session.commit()


async def _process_job(bot: Bot, job: BroadcastJob) -> None:
    # Avval "sending" holatiga o'tkazamiz — bot yuborish o'rtasida qayta ishga tushsa,
    # xabar hammaga ikkinchi marta yuborilib ketmasligi uchun.
    await _set_job(job.id, status="sending", sent_count=0)

    async with get_session() as session:
        users_result = await session.execute(select(User.tg_id).where(User.is_blocked == False))  # noqa: E712
        user_ids = [row[0] for row in users_result.all()]

    sent = 0
    for i, uid in enumerate(user_ids, start=1):
        if await _send_one(bot, uid, job):
            sent += 1
        if i % PROGRESS_SAVE_EVERY == 0:
            await _set_job(job.id, sent_count=sent)
        await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

    if job.to_channels:
        # Bot admin bo'lgan majburiy kanallarga ham post qilamiz — kanal obunachilari ham ko'radi
        async with get_session() as session:
            channel_ids = [row[0] for row in (await session.execute(select(Channel.chat_id))).all()]
        for chat_id in channel_ids:
            if await _send_one(bot, chat_id, job):
                sent += 1

    await _set_job(job.id, status="done", sent_count=sent)
    logger.info("Broadcast #%s yakunlandi: %s/%s", job.id, sent, len(user_ids))


async def _process_pending_jobs(bot: Bot) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(BroadcastJob).where(BroadcastJob.status == "pending").order_by(BroadcastJob.id)
        )
        jobs = list(result.scalars().all())

    for job in jobs:
        try:
            await _process_job(bot, job)
        except Exception:
            logger.exception("Broadcast #%s bajarilmadi", job.id)
            await _set_job(job.id, status="failed")


async def _mark_interrupted_jobs() -> None:
    """Oldingi ishga tushirishda yarim qolgan xabarlarni "failed" deb belgilaydi."""
    async with get_session() as session:
        await session.execute(
            update(BroadcastJob).where(BroadcastJob.status == "sending").values(status="failed")
        )
        await session.commit()


async def run_broadcast_worker(bot: Bot) -> None:
    try:
        await _mark_interrupted_jobs()
    except Exception:
        logger.exception("Yarim qolgan xabarlarni belgilab bo'lmadi")

    while True:
        try:
            await _process_pending_jobs(bot)
        except Exception:
            logger.exception("Broadcast worker'da xatolik")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
