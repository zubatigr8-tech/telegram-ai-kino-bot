"""Bot uchun klaviaturalar (tugmalar)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BTN_CHECK_SUB = "✅ Tekshirish"


def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        url = f"https://t.me/{ch.username}" if ch.username else None
        if url:
            rows.append([InlineKeyboardButton(text=ch.title or ch.username, url=url)])
    rows.append([InlineKeyboardButton(text=BTN_CHECK_SUB, callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
