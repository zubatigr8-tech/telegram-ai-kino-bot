"""Bot uchun klaviaturalar (tugmalar)."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

BTN_MOVIE = "🎬 Kino qidirish"
BTN_AI = "🧠 AI bilan suhbat"
BTN_HOME = "🏠 Bosh menyu"
BTN_CHECK_SUB = "✅ Tekshirish"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_MOVIE), KeyboardButton(text=BTN_AI)],
    ],
    resize_keyboard=True,
)

in_mode_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_HOME)]],
    resize_keyboard=True,
)


def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        url = f"https://t.me/{ch.username}" if ch.username else None
        if url:
            rows.append([InlineKeyboardButton(text=ch.title or ch.username, url=url)])
    rows.append([InlineKeyboardButton(text=BTN_CHECK_SUB, callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
