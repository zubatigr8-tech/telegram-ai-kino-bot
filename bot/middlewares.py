"""Bot middleware'lari:
- UserMiddleware: har bir foydalanuvchini bazaga yozadi va bloklanganlarni to'xtatadi;
- SubscriptionMiddleware: majburiy kanal obunasini tekshiradi."""
import datetime
import logging
from html import escape as h
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.keyboards import subscription_keyboard
from shared.config import settings
from shared.db.database import get_session
from shared.db.models import Channel, User, utcnow

logger = logging.getLogger(__name__)

EXEMPT_CALLBACKS = {"check_subscription"}
LAST_ACTIVE_UPDATE_INTERVAL = datetime.timedelta(minutes=5)


async def get_active_channels() -> list[Channel]:
    async with get_session() as session:
        result = await session.execute(select(Channel).where(Channel.is_active == True))  # noqa: E712
        return list(result.scalars().all())


async def is_subscribed(bot, user_id: int, channels: list[Channel]) -> bool:
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.chat_id, user_id)
        except Exception:
            logger.warning(
                "Obunani tekshirib bo'lmadi (chat_id=%s). Bot o'sha kanalda admin ekanini tekshiring.",
                ch.chat_id,
            )
            return False
        if member.status in ("member", "administrator", "creator"):
            continue
        # "restricted" — cheklangan, lekin kanal a'zosi bo'lib qolishi mumkin
        if member.status == "restricted" and getattr(member, "is_member", False):
            continue
        return False
    return True


async def upsert_user(tg_user: TgUser) -> tuple[bool, bool]:
    """Foydalanuvchini bazaga yozadi/yangilaydi. (is_new, is_blocked) qaytaradi."""
    async with get_session() as session:
        user = await session.get(User, tg_user.id)
        if user is None:
            session.add(User(tg_id=tg_user.id, username=tg_user.username, full_name=tg_user.full_name))
            try:
                await session.commit()
            except IntegrityError:
                # Bir vaqtda kelgan ikki xabar — foydalanuvchi allaqachon yozib bo'lingan
                await session.rollback()
                return False, False
            return True, False

        changed = False
        if user.username != tg_user.username or user.full_name != tg_user.full_name:
            user.username = tg_user.username
            user.full_name = tg_user.full_name
            changed = True
        now = utcnow()
        last_active = user.last_active
        if last_active is not None and last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=datetime.timezone.utc)  # SQLite tz'ni saqlamaydi
        if last_active is None or now - last_active > LAST_ACTIVE_UPDATE_INTERVAL:
            user.last_active = now
            changed = True
        if changed:
            await session.commit()
        return False, user.is_blocked


async def notify_admins_new_user(bot, tg_user: TgUser) -> None:
    label = f"@{tg_user.username}" if tg_user.username else (tg_user.full_name or "—")
    text = (
        "🆕 <b>Yangi obunachi!</b>\n\n"
        f"👤 {h(label)}\n"
        f"ID: <code>{tg_user.id}</code>"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass  # admin botni hali /start qilmagan bo'lishi mumkin — o'tkazib yuboramiz


class UserMiddleware(BaseMiddleware):
    """Outer middleware: /start bosmagan bo'lsa ham foydalanuvchini bazaga yozadi
    (aks holda u broadcast'dan tushib qoladi) va bloklangan foydalanuvchini to'xtatadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = data.get("event_chat")
        bot = data.get("bot")

        # Faqat shaxsiy chatdagi foydalanuvchilarni hisobga olamiz
        if user is None or user.is_bot or (chat is not None and chat.type != "private"):
            return await handler(event, data)

        try:
            is_new, is_blocked = await upsert_user(user)
        except Exception:
            logger.exception("Foydalanuvchini bazaga yozib bo'lmadi: %s", user.id)
            return await handler(event, data)

        if is_new and bot is not None:
            await notify_admins_new_user(bot, user)

        if is_blocked and user.id not in settings.ADMIN_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("🚫 Siz botdan foydalanishdan bloklangansiz.")
            return None

        return await handler(event, data)


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        bot = data.get("bot")

        if user is None or bot is None:
            return await handler(event, data)

        if user.id in settings.ADMIN_IDS:
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data in EXEMPT_CALLBACKS:
            return await handler(event, data)

        channels = await get_active_channels()
        if not channels:
            return await handler(event, data)

        if await is_subscribed(bot, user.id, channels):
            return await handler(event, data)

        text = (
            "📢 Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'ling, "
            "so'ng \"✅ Tekshirish\" tugmasini bosing:"
        )
        kb = subscription_keyboard(channels)
        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.answer("Hali barcha kanallarga obuna bo'lmagansiz.", show_alert=True)
            if event.message:
                await event.message.answer(text, reply_markup=kb)
        return None
