"""Bot uchun klaviaturalar (tugmalar)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.channels import channel_url

BTN_CHECK_SUB = "✅ Tekshirish"


def subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    rows = []
    for i, ch in enumerate(channels, start=1):
        url = channel_url(ch)
        if url:
            rows.append([InlineKeyboardButton(text=ch.title or f"{i}-kanal", url=url)])
    rows.append([InlineKeyboardButton(text=BTN_CHECK_SUB, callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
