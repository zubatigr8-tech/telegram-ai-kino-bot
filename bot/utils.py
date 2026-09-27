"""Bot handlerlari uchun umumiy yordamchi funksiyalar."""
from aiogram.types import Message

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_text(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Uzun matnni Telegram limitiga sig'adigan bo'laklarga ajratadi (iloji bo'lsa qator oxiridan)."""
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


async def answer_plain(message: Message, text: str) -> None:
    """AI javobini oddiy matn sifatida yuboradi.

    AI javobida "<", "&" yoki markdown belgilari bo'lishi mumkin — HTML rejimida
    Telegram ularni xato deb rad etadi va foydalanuvchi hech narsa olmaydi.
    Shuning uchun parse_mode o'chiriladi va uzun javoblar bo'laklarga bo'linadi."""
    text = text.strip() or "🤔 Javob topa olmadim, savolni boshqacharoq yozib ko'ring."
    for part in split_text(text):
        await message.answer(part, parse_mode=None)
