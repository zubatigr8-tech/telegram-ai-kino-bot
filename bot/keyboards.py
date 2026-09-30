"""Bot uchun klaviaturalar (tugmalar)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.channels import channel_url

BTN_CHECK_SUB = "✅ Tekshirish"

# ---------- Foydalanuvchi menyusi ----------
BTN_SHORTS = "🎬 Shorts"
BTN_PREMIUM = "💎 Premium"
BTN_ADMIN_PANEL = "📋 Boshqarish"

# ---------- Admin panel (pastki tugmalar) ----------
BTN_CHANNELS = "📣 Kanallarni sozlash"
BTN_STATS = "📈 Statistika"
BTN_BROADCAST = "✉️ Xabar yuborish"
BTN_BOT_STATUS = "🤖 Bot holati"
BTN_MOVIE_ADD = "📥 Kino yuklash"
BTN_MOVIE_DEL = "🗑 Kino o'chirish"
BTN_MOVIE_POST = "📣 Kino postini yuborish"
BTN_MOVIE_EDIT = "✏️ Kino tahrirlash"
BTN_SHORT_ADD = "🎬 Shorts yuklash"
BTN_SHORT_DEL = "🗑 Shorts o'chirish"
BTN_CARD = "💳 Karta sozlamalari"
BTN_MANAGE = "👤 Boshqarish"
BTN_ADMINS = "👑 Adminlar ro'yxati"
BTN_PREMIUMS = "💎 Premiumlar ro'yxati"
BTN_PREMIUM_STATUS = "🔄 Premium holati"
BTN_HOME = "🏠 Bosh sahifa"

ADMIN_BUTTONS = [
    [BTN_CHANNELS, BTN_STATS],
    [BTN_BROADCAST, BTN_BOT_STATUS],
    [BTN_MOVIE_ADD, BTN_MOVIE_DEL],
    [BTN_MOVIE_POST, BTN_MOVIE_EDIT],
    [BTN_SHORT_ADD, BTN_SHORT_DEL],
    [BTN_CARD, BTN_MANAGE],
    [BTN_ADMINS, BTN_PREMIUMS],
    [BTN_PREMIUM_STATUS, BTN_HOME],
]
ADMIN_BUTTON_TEXTS = {text for row in ADMIN_BUTTONS for text in row}


def _reply_kb(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return _reply_kb(ADMIN_BUTTONS)


def user_menu_kb(is_admin: bool, premium_enabled: bool) -> ReplyKeyboardMarkup:
    row = [BTN_SHORTS]
    if premium_enabled:
        row.append(BTN_PREMIUM)
    rows = [row]
    if is_admin:
        rows.append([BTN_ADMIN_PANEL])
    return _reply_kb(rows)


def subscription_keyboard(channels: list, show_premium: bool = False) -> InlineKeyboardMarkup:
    rows = []
    for i, ch in enumerate(channels, start=1):
        url = channel_url(ch)
        if url:
            rows.append([InlineKeyboardButton(text=ch.title or f"{i}-kanal", url=url)])
    rows.append([InlineKeyboardButton(text=BTN_CHECK_SUB, callback_data="check_subscription")])
    if show_premium:
        rows.append([InlineKeyboardButton(text="💎 Obunasiz foydalanish (Premium)", callback_data="prem:info")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
