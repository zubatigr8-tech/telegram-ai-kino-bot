from html import escape as h

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select

from bot.keyboards import BTN_MOVIE, in_mode_menu
from bot.states import UserFlow
from shared.db.database import get_session
from shared.db.models import Movie

router = Router(name="movie")


@router.message(F.text == BTN_MOVIE)
async def start_movie_search(message: Message, state: FSMContext) -> None:
    await state.set_state(UserFlow.movie_search)
    await message.answer(
        "Kino kodini (raqamini) yuboring, masalan: <b>7</b>\n\n"
        "Bosh menyuga qaytish uchun pastdagi tugmani bosing.",
        reply_markup=in_mode_menu,
    )


@router.message(UserFlow.movie_search, F.text.regexp(r"^\d+$"))
async def search_movie(message: Message) -> None:
    code = int(message.text)
    async with get_session() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        movie = result.scalar_one_or_none()

    if movie is None:
        await message.answer(f"❌ <b>{code}</b> raqamli kino topilmadi. Boshqa raqam yuboring.")
        return

    caption = f"🎬 <b>{h(movie.title)}</b>\n\n{h(movie.description or '')}".strip()
    if movie.file_type == "document":
        await message.answer_document(movie.file_id, caption=caption)
    else:
        await message.answer_video(movie.file_id, caption=caption)


@router.message(UserFlow.movie_search)
async def wrong_movie_input(message: Message) -> None:
    await message.answer("Iltimos, faqat kino kodini (raqam) yuboring. Masalan: 7")
