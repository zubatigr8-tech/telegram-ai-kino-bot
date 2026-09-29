"""Antiradar bot klaviaturalari."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from antiradar.i18n import LANGUAGES, t

SPEED_OPTIONS = (60, 70, 80, 90, 100, 110, 120)


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "menu_subscription")), KeyboardButton(text=t(lang, "menu_settings"))],
            [KeyboardButton(text=t(lang, "menu_help"))],
        ],
        resize_keyboard=True,
    )


def language_keyboard(suggested: str) -> InlineKeyboardMarkup:
    # Telegram ilovasi tiliga mos til birinchi turadi
    codes = [suggested] + [c for c in LANGUAGES if c != suggested]
    rows = [[InlineKeyboardButton(text=LANGUAGES[c], callback_data=f"lang:{c}")] for c in codes]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(lang: str, signs_enabled: bool) -> InlineKeyboardMarkup:
    signs_state = t(lang, "state_on" if signs_enabled else "state_off")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="set:lang")],
            [InlineKeyboardButton(text=t(lang, "btn_max_speed"), callback_data="set:speed")],
            [InlineKeyboardButton(text=t(lang, "btn_signs", state=signs_state), callback_data="set:signs")],
        ]
    )


def speed_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=str(s), callback_data=f"spd:{s}") for s in SPEED_OPTIONS]
    rows = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    rows.append([InlineKeyboardButton(text=t(lang, "btn_off"), callback_data="spd:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_keyboard(lang: str, url: str, price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_pay", price=price), url=url)]]
    )
