from html import escape as h

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select, update

from shared.db.database import get_session
from shared.db.models import Movie

router = Router(name="movie")

MAX_CODE_DIGITS = 9  # bazadagi Integer ustuniga sig'adigan xavfsiz uzunlik


def movie_caption(movie: Movie) -> str:
    description = movie.description or ""
    if len(description) > 700:  # Telegram caption limiti 1024 belgi
        description = description[:700] + "…"
    return f"🎬 <b>{h(movie.title)}</b>\n\n{h(description)}".strip()


async def send_movie(bot: Bot, chat_id: int, code: int) -> bool:
    """Kinoni kod bo'yicha yuboradi va ko'rishlar sonini oshiradi. Topilmasa False."""
    async with get_session() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        movie = result.scalar_one_or_none()
        if movie is None:
            return False
        await session.execute(update(Movie).where(Movie.id == movie.id).values(views=Movie.views + 1))
        await session.commit()

    caption = movie_caption(movie)
    if movie.file_type == "document":
        await bot.send_document(chat_id, movie.file_id, caption=caption)
    else:
        await bot.send_video(chat_id, movie.file_id, caption=caption)
    return True


@router.message(F.text.regexp(r"^\d+$"))
async def search_movie(message: Message) -> None:
    if len(message.text) > MAX_CODE_DIGITS or not await send_movie(message.bot, message.chat.id, int(message.text)):
        await message.answer(f"❌ <b>{h(message.text)}</b> raqamli kino topilmadi. Boshqa raqam yuboring.")


@router.message()
async def not_a_code(message: Message) -> None:
    # Kino kodidan boshqa har qanday xabar (matn, rasm, fayl, stiker...) uchun yo'riqnoma
    await message.answer("🎬 Iltimos, faqat kino kodini (raqamini) yuboring, masalan: <b>7</b>")
