"""Har bir yangilanishda foydalanuvchini bazadan oladi (yo'q bo'lsa yaratadi) va handlerga `db_user` qilib beradi.
Til hali tanlanmagan bo'lsa, avval tilni tanlashni so'raydi."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.exc import IntegrityError

from antiradar.db import User, get_session
from antiradar.i18n import detect_lang, t
from antiradar.keyboards import language_keyboard


async def load_user(tg_user) -> User:
    async with get_session() as session:
        user = await session.get(User, tg_user.id)
        if user is None:
            user = User(tg_id=tg_user.id, username=tg_user.username, full_name=tg_user.full_name)
            session.add(user)
            try:
                await session.commit()
            except IntegrityError:
                # Bir vaqtda kelgan ikki yangilanish — foydalanuvchi allaqachon yozilgan
                await session.rollback()
                user = await session.get(User, tg_user.id)
        elif user.username != tg_user.username or user.full_name != tg_user.full_name:
            user.username, user.full_name = tg_user.username, tg_user.full_name
            await session.commit()
        return user


def _is_onboarding(event: TelegramObject) -> bool:
    if isinstance(event, Message):
        # To'lov xabari til tanlanmagan bo'lsa ham qabul qilinishi shart
        return bool(event.successful_payment) or bool(event.text and event.text.split()[0].split("@")[0] == "/start")
    if isinstance(event, CallbackQuery):
        return bool(event.data and event.data.startswith("lang:"))
    return True  # pre_checkout_query va boshqalar


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user = await load_user(tg_user)
        if user.is_blocked:
            return None

        if user.lang is None and not _is_onboarding(event):
            lang = detect_lang(tg_user.language_code)
            if isinstance(event, Message) and event.edit_date is None:
                await event.answer(t(lang, "choose_language"), reply_markup=language_keyboard(lang))
            elif isinstance(event, CallbackQuery):
                await event.answer()
            return None

        data["db_user"] = user
        return await handler(event, data)
