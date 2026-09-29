"""Sozlamalar: til va shaxsiy tezlik chegarasi."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from antiradar.db import User, get_session
from antiradar.i18n import LANGUAGES, all_variants, t
from antiradar.keyboards import SPEED_OPTIONS, language_keyboard, settings_keyboard, speed_keyboard

router = Router(name="settings")


def settings_text(user: User) -> str:
    max_speed = f"{user.max_speed} km/h" if user.max_speed else t(user.lang, "max_speed_off")
    return t(user.lang, "settings_title", lang=LANGUAGES[user.lang], max_speed=max_speed)


@router.message(Command("settings"))
@router.message(F.text.in_(all_variants("menu_settings")))
async def cmd_settings(message: Message, db_user: User) -> None:
    await message.answer(settings_text(db_user), reply_markup=settings_keyboard(db_user.lang))


@router.callback_query(F.data == "set:lang")
async def change_language(callback: CallbackQuery, db_user: User) -> None:
    await callback.answer()
    await callback.message.answer(t(db_user.lang, "choose_language"), reply_markup=language_keyboard(db_user.lang))


@router.callback_query(F.data == "set:speed")
async def change_speed(callback: CallbackQuery, db_user: User) -> None:
    await callback.answer()
    await callback.message.answer(t(db_user.lang, "max_speed_choose"), reply_markup=speed_keyboard(db_user.lang))


@router.callback_query(F.data.startswith("spd:"))
async def set_speed(callback: CallbackQuery, db_user: User) -> None:
    raw = callback.data.split(":", 1)[1]
    value = int(raw) if raw.isdigit() else -1
    if value != 0 and value not in SPEED_OPTIONS:
        await callback.answer()
        return
    async with get_session() as session:
        user = await session.get(User, db_user.tg_id)
        user.max_speed = value or None
        await session.commit()
    await callback.answer(t(user.lang, "saved"))
    await callback.message.edit_text(settings_text(user), reply_markup=settings_keyboard(user.lang))
