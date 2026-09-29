from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    # Havola yoki qidiruv matnidan boshqa har qanday xabar (rasm, stiker, juda qisqa matn...) uchun yo'riqnoma
    await message.answer(
        "🔗 Menga <b>Instagram</b>, <b>YouTube</b> yoki <b>TikTok</b> videosining havolasini yuboring — "
        "videosi va undagi qo'shiqni topib beraman 🎵\n\n"
        "✍️ Yoki qo'shiq nomi yoki matnidan parcha yozing",
        reply_markup=ReplyKeyboardRemove(),
    )
