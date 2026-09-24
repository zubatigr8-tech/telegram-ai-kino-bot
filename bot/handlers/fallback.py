"""Boshqa hech qaysi handlerga to'g'ri kelmagan xabarlar uchun standart javob.
Bu router ENG OXIRIDA ro'yxatga olinishi kerak (main.py'da), aks holda
boshqa handlerlarni "yeb qo'yadi"."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards import main_menu

router = Router(name="fallback")


@router.message(F.text)
async def unknown_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Tushunmadim 🤔 Quyidagi tugmalardan birini tanlang:",
        reply_markup=main_menu,
    )
