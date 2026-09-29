"""/start → tilni tanlash → bepul sinov va yo'riqnoma."""
import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from antiradar.config import settings
from antiradar.db import User, get_session, utcnow
from antiradar.handlers import fmt_date
from antiradar.i18n import LANGUAGES, all_variants, detect_lang, t
from antiradar.keyboards import language_keyboard, main_menu

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User) -> None:
    lang = db_user.lang or detect_lang(message.from_user.language_code)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard(lang))


@router.callback_query(F.data.startswith("lang:"))
async def choose_language(callback: CallbackQuery, db_user: User) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGUAGES:
        await callback.answer()
        return

    trial_granted = False
    async with get_session() as session:
        user = await session.get(User, db_user.tg_id)
        user.lang = lang
        # Sinov davri har bir foydalanuvchiga faqat bir marta beriladi
        if user.trial_until is None:
            user.trial_until = utcnow() + datetime.timedelta(days=settings.TRIAL_DAYS)
            trial_granted = True
        await session.commit()
        trial_until = user.trial_until

    await callback.answer()
    await callback.message.edit_text(LANGUAGES[lang])
    if trial_granted:
        text = t(lang, "welcome", days=settings.TRIAL_DAYS, date=fmt_date(trial_until)) + "\n\n" + t(lang, "how_to")
    else:
        text = t(lang, "saved")
    await callback.message.answer(text, reply_markup=main_menu(lang))


@router.message(Command("help"))
@router.message(F.text.in_(all_variants("menu_help")))
async def cmd_help(message: Message, db_user: User) -> None:
    await message.answer(t(db_user.lang, "how_to"), reply_markup=main_menu(db_user.lang))
