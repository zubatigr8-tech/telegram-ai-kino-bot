"""Kanal zayavkalari (qo'shilish so'rovlari): yig'ish, statistika, bosqich bildirishnomalari
va hammasini bitta buyruq bilan tasdiqlash."""
import asyncio
import logging
from html import escape as h

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select, update

from bot.services import AUTO_APPROVE, all_admin_ids, get_setting, is_admin
from shared.db.database import get_session
from shared.db.models import Channel, JoinRequest

logger = logging.getLogger(__name__)

APPROVE_DELAY = 0.05  # Telegram flood limitiga tushmaslik uchun har bir tasdiqlash orasidagi pauza
_running: set[int] = set()  # hozir "hammasini tasdiqlash" ketayotgan kanallar (chat_id)


def next_milestone(last: int) -> int:
    """1000 → 5000 → 10000 → 20000 → 30000 ..."""
    for step in (1000, 5000, 10000):
        if last < step:
            return step
    return (last // 10000 + 1) * 10000


def can_manage(user_id: int, channel: Channel) -> bool:
    return is_admin(user_id) or (channel.owner_id is not None and channel.owner_id == user_id)


async def get_channel_by_chat(chat_id: int) -> Channel | None:
    async with get_session() as session:
        return (await session.execute(select(Channel).where(Channel.chat_id == chat_id))).scalar_one_or_none()


async def owned_channels(user_id: int) -> list[Channel]:
    async with get_session() as session:
        return list((await session.execute(select(Channel).where(Channel.owner_id == user_id))).scalars())


async def has_pending_request(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        row = await session.execute(
            select(JoinRequest.id)
            .where(JoinRequest.user_id == user_id, JoinRequest.chat_id == chat_id)
            .where(JoinRequest.approved == False, JoinRequest.failed == False)  # noqa: E712
            .limit(1)
        )
        return row.first() is not None


async def request_counts(chat_id: int) -> tuple[int, int, int]:
    """(kutilayotgan, tasdiqlangan, jami) zayavkalar soni."""
    async with get_session() as session:
        async def count(*conds):
            stmt = select(func.count(JoinRequest.id)).where(JoinRequest.chat_id == chat_id, *conds)
            return (await session.execute(stmt)).scalar_one()

        pending = await count(JoinRequest.approved == False, JoinRequest.failed == False)  # noqa: E712
        approved = await count(JoinRequest.approved == True)  # noqa: E712
        total = await count()
    return pending, approved, total


async def channel_stats_text(bot: Bot, channel: Channel) -> str:
    try:
        members = await bot.get_chat_member_count(channel.chat_id)
    except Exception:
        members = None
    pending, approved, total = await request_counts(channel.chat_id)
    lines = [
        f"📣 <b>{h(channel.title or str(channel.chat_id))}</b>",
        f"👥 Kanaldagi obunachilar: <b>{members if members is not None else '— (bot admin emas)'}</b>",
        f"📨 Bot orqali kelgan zayavkalar: <b>{total}</b>",
        f"⏳ Tasdiq kutayotganlar: <b>{pending}</b>",
        f"✅ Tasdiqlanganlar: <b>{approved}</b>",
        f"⚙️ Rejim: {'zayavkalar yig‘iladi' if channel.collect_requests else 'avtomatik tasdiqlash'}",
    ]
    if channel.collect_requests:
        lines.append(f"🎯 Keyingi bildirishnoma: <b>{next_milestone(channel.last_milestone or 0)}</b> zayavkada")
    if channel.chat_id in _running:
        lines.append("\n🔄 <i>Hozir tasdiqlanmoqda...</i>")
    return "\n".join(lines)


def approve_kb(channel: Channel, pending: int) -> InlineKeyboardMarkup:
    rows = []
    if pending:
        rows.append([InlineKeyboardButton(text=f"✅ Hammasini tasdiqlash ({pending})", callback_data=f"jr:all:{channel.id}")])
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"jr:view:{channel.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def notify_managers(bot: Bot, channel: Channel, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    recipients = set(all_admin_ids())
    if channel.owner_id:
        recipients.add(channel.owner_id)
    for uid in recipients:
        try:
            await bot.send_message(uid, text, reply_markup=kb)
        except Exception:
            pass  # botni /start qilmagan bo'lishi mumkin


async def _check_milestone(bot: Bot, channel: Channel) -> None:
    pending, _, total = await request_counts(channel.chat_id)
    last = channel.last_milestone or 0
    milestone = next_milestone(last)
    if total < milestone:
        return
    # Bir vaqtda kelgan bir nechta zayavka bitta bosqichni ikki marta bildirmasligi uchun shartli yangilash
    async with get_session() as session:
        result = await session.execute(
            update(Channel)
            .where(Channel.id == channel.id, Channel.last_milestone == last)
            .values(last_milestone=milestone)
        )
        await session.commit()
    if result.rowcount != 1:
        return
    channel.last_milestone = milestone
    await notify_managers(
        bot,
        channel,
        f"🎉 <b>{h(channel.title or str(channel.chat_id))}</b> kanaliga bot orqali <b>{total}</b> ta zayavka yig'ildi!\n\n"
        f"⏳ Tasdiq kutayotganlar: <b>{pending}</b>\n\nHammasini bitta tugma bilan tasdiqlashingiz mumkin:",
        approve_kb(channel, pending),
    )


async def handle_join_request(request: ChatJoinRequest) -> tuple[bool, bool]:
    """Zayavkani qayta ishlaydi. (bizning kanalmi, darhol tasdiqlandimi) qaytaradi."""
    channel = await get_channel_by_chat(request.chat.id)
    if channel is None:
        return False, False

    approved = False
    if not channel.collect_requests and (await get_setting(AUTO_APPROVE, "1")) == "1":
        try:
            await request.approve()
            approved = True
        except Exception as exc:
            logger.warning("Zayavkani tasdiqlab bo'lmadi (chat=%s): %s", request.chat.id, exc)

    if approved or not await has_pending_request(request.from_user.id, request.chat.id):
        async with get_session() as session:
            session.add(JoinRequest(user_id=request.from_user.id, chat_id=request.chat.id, approved=approved))
            await session.commit()

    if channel.collect_requests:
        await _check_milestone(request.bot, channel)
    return True, approved


async def _approve_all(bot: Bot, channel: Channel, report_chat_id: int) -> None:
    approved = failed = 0
    try:
        while True:
            async with get_session() as session:
                batch = list(
                    (
                        await session.execute(
                            select(JoinRequest)
                            .where(JoinRequest.chat_id == channel.chat_id)
                            .where(JoinRequest.approved == False, JoinRequest.failed == False)  # noqa: E712
                            .order_by(JoinRequest.id)
                            .limit(200)
                        )
                    ).scalars()
                )
            if not batch:
                break
            for jr in batch:
                ok = False
                for _ in range(3):
                    try:
                        await bot.approve_chat_join_request(channel.chat_id, jr.user_id)
                        ok = True
                        break
                    except TelegramRetryAfter as exc:
                        await asyncio.sleep(exc.retry_after)
                    except Exception as exc:
                        # Foydalanuvchi so'rovni bekor qilgan yoki allaqachon a'zo bo'lgan
                        if "USER_ALREADY_PARTICIPANT" in str(exc):
                            ok = True
                        break
                async with get_session() as session:
                    await session.execute(
                        update(JoinRequest).where(JoinRequest.id == jr.id).values(approved=ok, failed=not ok)
                    )
                    await session.commit()
                approved += ok
                failed += not ok
                await asyncio.sleep(APPROVE_DELAY)
    except Exception:
        logger.exception("Zayavkalarni tasdiqlashda xatolik (chat=%s)", channel.chat_id)
    finally:
        _running.discard(channel.chat_id)

    text = (
        f"✅ <b>{h(channel.title or str(channel.chat_id))}</b>: zayavkalarni tasdiqlash tugadi.\n\n"
        f"Tasdiqlandi: <b>{approved}</b>"
        + (f"\nTasdiqlab bo'lmadi (so'rov bekor qilingan): <b>{failed}</b>" if failed else "")
    )
    try:
        await bot.send_message(report_chat_id, text)
    except Exception:
        pass


def start_approve_all(bot: Bot, channel: Channel, report_chat_id: int) -> bool:
    """Fon rejimida hammasini tasdiqlashni boshlaydi. Allaqachon ketayotgan bo'lsa False."""
    if channel.chat_id in _running:
        return False
    _running.add(channel.chat_id)
    asyncio.create_task(_approve_all(bot, channel, report_chat_id))
    return True


async def create_request_link(bot: Bot, channel: Channel) -> str:
    """Zayavka talab qiladigan taklif havolasini yaratadi (bot kanalda admin bo'lishi kerak)."""
    link = await bot.create_chat_invite_link(channel.chat_id, name="Kino bot zayavka", creates_join_request=True)
    return link.invite_link
