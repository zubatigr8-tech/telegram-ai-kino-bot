from html import escape as h

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select

from shared.db.database import get_session
from shared.db.models import Movie

router = Router(name="movie")

MAX_CODE_DIGITS = 9  # bazadagi Integer ustuniga sig'adigan xavfsiz uzunlik


@router.message(F.text.regexp(r"^\d+$"))
async def search_movie(message: Message) -> None:
    if len(message.text) > MAX_CODE_DIGITS:
        await message.answer(f"❌ <b>{h(message.text)}</b> raqamli kino topilmadi. Boshqa raqam yuboring.")
        return

    code = int(message.text)
    async with get_session() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        movie = result.scalar_one_or_none()

    if movie is None:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi. Boshqa raqam yuboring.")
        return

    description = movie.description or ""
    if len(description) > 700:  # Telegram caption limiti 1024 belgi
        description = description[:700] + "…"
    caption = f"🎬 <b>{h(movie.title)}</b>\n\n{h(description)}".strip()
    if movie.file_type == "document":
        await message.answer_document(movie.file_id, caption=caption)
    else:
        await message.answer_video(movie.file_id, caption=caption)


@router.message()
async def not_a_code(message: Message) -> None:
    # Kino kodi yoki havoladan boshqa har qanday xabar (matn, rasm, fayl, stiker...) uchun yo'riqnoma
    await message.answer(
        "🤖 Menga quyidagilardan birini yuboring:\n\n"
        "🔗 <b>Instagram</b>, <b>YouTube</b> yoki <b>TikTok</b> havolasi — videosi va qo'shig'ini topib beraman\n"
        "🎬 Kino kodi (raqam), masalan: <b>7</b>",
        reply_markup=ReplyKeyboardRemove(),
    )
