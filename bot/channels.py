"""Majburiy kanallar bilan ishlash: ma'lumotni Telegram'dan olish, havola yaratish, obunani tekshirish."""
import logging
import re
import time
from html import escape as h

from aiogram import Bot
from sqlalchemy import select

from bot.join_requests import create_request_link, has_pending_request, mark_joined
from bot.services import all_admin_ids

from shared.db.database import get_session
from shared.db.models import Channel

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
ADMIN_WARNING_INTERVAL = 6 * 60 * 60  # bir xil ogohlantirish adminga 6 soatda ko'pi bilan bir marta
_last_warning: dict[int, float] = {}


class ChannelError(Exception):
    """Kanalni qo'shib bo'lmasligi sababi (admin uchun tushunarli matn)."""


def clean_username(raw: str | None) -> str | None:
    """"@kanal", "t.me/kanal", "https://t.me/kanal" → "kanal". Noto'g'ri bo'lsa None."""
    if not raw:
        return None
    value = raw.strip()
    value = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", value)
    value = value.lstrip("@").split("/")[0].split("?")[0]
    return value if USERNAME_RE.match(value) else None


def channel_url(channel: Channel) -> str | None:
    # Foydalanuvchiga zayavka talab qiladigan maxsus havola beriladi — zayavkalar yig'ilib turadi
    # va ularni faqat kanal admini tasdiqlaydi
    if channel.request_link:
        return channel.request_link
    username = clean_username(channel.username)
    if username:
        return f"https://t.me/{username}"
    return channel.invite_link or None


async def get_active_channels() -> list[Channel]:
    async with get_session() as session:
        result = await session.execute(select(Channel).where(Channel.is_active == True))  # noqa: E712
        return list(result.scalars().all())


async def fetch_channel_info(bot: Bot, chat_ref: int | str) -> dict:
    """Kanal ma'lumotini Telegram'dan oladi va bot kanalda admin ekanini tekshiradi.
    chat_ref — chat ID (-100...) yoki "@username"."""
    try:
        chat = await bot.get_chat(chat_ref)
    except Exception:
        raise ChannelError(
            "Kanal topilmadi. Botni kanalga <b>admin</b> qilib qo'shganingizni va "
            "ID/username to'g'ri ekanini tekshiring."
        )

    me = await bot.me()
    try:
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception:
        member = None
    if member is None or member.status not in ("administrator", "creator"):
        raise ChannelError(
            f"Bot «{h(chat.title or str(chat.id))}» kanalida <b>admin emas</b>. "
            "Avval botni kanalga admin qilib qo'shing, keyin qayta urinib ko'ring."
        )

    invite_link = None
    if not chat.username:
        # Yopiq kanal — foydalanuvchilar qo'shila olishi uchun taklif havolasi kerak
        invite_link = chat.invite_link
        if not invite_link:
            try:
                link = await bot.create_chat_invite_link(chat.id, name="Kino bot")
                invite_link = link.invite_link
            except Exception:
                raise ChannelError(
                    "Kanal yopiq, lekin bot taklif havolasini yarata olmadi. Botga kanalda "
                    "<b>\"Foydalanuvchilarni taklif qilish\"</b> huquqini bering."
                )

    return {
        "chat_id": chat.id,
        "username": chat.username,
        "title": chat.title,
        "invite_link": invite_link,
    }


async def ensure_channel_links(bot: Bot, channels: list[Channel]) -> None:
    """Havolasi yo'q yoki noto'g'ri kanallar uchun ma'lumotni Telegram'dan olib, bazaga yozadi.
    Masalan, username o'rniga kanal nomi yozib qo'yilgan eski yozuvlar shu yerda o'zi tuzaladi."""
    for ch in channels:
        if not ch.request_link:
            # Zayavka havolasi hali yaratilmagan (bot kanalda "Add members" huquqiga ega bo'lishi kerak)
            try:
                link = await create_request_link(bot, ch)
            except Exception as exc:
                logger.warning("Zayavka havolasini yaratib bo'lmadi (chat_id=%s): %s", ch.chat_id, exc)
            else:
                async with get_session() as session:
                    db_ch = await session.get(Channel, ch.id)
                    if db_ch is not None:
                        db_ch.request_link = link
                        await session.commit()
                ch.request_link = link
        if channel_url(ch):
            continue
        try:
            info = await fetch_channel_info(bot, ch.chat_id)
        except Exception as exc:
            logger.warning("Kanal havolasini olib bo'lmadi (chat_id=%s): %s", ch.chat_id, exc)
            continue
        async with get_session() as session:
            db_ch = await session.get(Channel, ch.id)
            if db_ch is None:
                continue
            db_ch.username = info["username"]
            db_ch.invite_link = info["invite_link"]
            db_ch.title = db_ch.title or info["title"]
            await session.commit()
        ch.username, ch.invite_link, ch.title = info["username"], info["invite_link"], ch.title or info["title"]
        logger.info("Kanal havolasi yangilandi: %s → %s", ch.chat_id, channel_url(ch))


async def _warn_admins(bot: Bot, channel: Channel) -> None:
    now = time.monotonic()
    if now - _last_warning.get(channel.chat_id, -ADMIN_WARNING_INTERVAL) < ADMIN_WARNING_INTERVAL:
        return
    _last_warning[channel.chat_id] = now
    text = (
        "⚠️ <b>Obunani tekshirib bo'lmayapti!</b>\n\n"
        f"Kanal: {h(channel.title or str(channel.chat_id))} (<code>{channel.chat_id}</code>)\n\n"
        "Bot bu kanalda admin emas yoki kanaldan chiqarilgan. Toki tuzatilmaguncha "
        "bu kanal obuna tekshiruvida hisobga olinmaydi.\n"
        "Botni kanalga admin qilib qo'shing."
    )
    for admin_id in all_admin_ids():
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def is_subscribed(bot: Bot, user_id: int, channels: list[Channel]) -> bool:
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.chat_id, user_id)
        except Exception as exc:
            # Bot kanalda admin bo'lmasa, obunani umuman tekshirib bo'lmaydi. Bunday holda
            # barcha foydalanuvchilarni to'sib qo'ymaslik uchun kanalni o'tkazib yuboramiz
            # va adminlarni ogohlantiramiz.
            logger.warning("Obunani tekshirib bo'lmadi (chat_id=%s): %s", ch.chat_id, exc)
            await _warn_admins(bot, ch)
            continue
        if member.status in ("member", "administrator", "creator"):
            if await has_pending_request(user_id, ch.chat_id):
                await mark_joined(user_id, ch.chat_id)  # admin zayavkani Telegram'da qo'lda tasdiqlagan
            continue
        # "restricted" — cheklangan, lekin kanal a'zosi bo'lib qolishi mumkin
        if member.status == "restricted" and getattr(member, "is_member", False):
            continue
        # Zayavka yuborgan foydalanuvchi obuna bo'lgan hisoblanadi
        # (so'rovni kanal admini keyinroq o'zi tasdiqlaydi)
        if await has_pending_request(user_id, ch.chat_id):
            continue
        return False
    return True
