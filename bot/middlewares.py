"""Har bir xabar/tugma bosilishida majburiy kanal obunasini tekshiradigan middleware."""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from bot.keyboards import subscription_keyboard
from shared.config import settings
from shared.db.database import get_session
from shared.db.models import Channel

logger = logging.getLogger(__name__)

EXEMPT_CALLBACKS = {"check_subscription"}


async def get_active_channels() -> list[Channel]:
    async with get_session() as session:
        result = await session.execute(select(Channel).where(Channel.is_active == True))  # noqa: E712
        return list(result.scalars().all())


async def is_subscribed(bot, user_id: int, channels: list[Channel]) -> bool:
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.chat_id, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            logger.warning(
                "Obunani tekshirib bo'lmadi (chat_id=%s). Bot o'sha kanalda admin ekanini tekshiring.",
                ch.chat_id,
            )
            return False
    return True


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
