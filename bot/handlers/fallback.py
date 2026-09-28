from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    # Havoladan boshqa har qanday xabar (matn, rasm, fayl, stiker...) uchun yo'riqnoma
    await message.answer(
        "🔗 Menga <b>Instagram</b>, <b>YouTube</b> yoki <b>TikTok</b> videosining havolasini yuboring — "
        "videosi va undagi qo'shiqni topib beraman 🎵",
        reply_markup=ReplyKeyboardRemove(),
    )
