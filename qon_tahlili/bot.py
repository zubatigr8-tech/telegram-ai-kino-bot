"""Qon tahlili boti: jins va yoshni so'raydi, natijalarni (matn yoki rasm) qabul qilib, xulosa beradi.

Ishga tushirish: python -m qon_tahlili.bot   (.env da QON_BOT_TOKEN bo'lishi kerak)

Maxfiylik: tahlil natijalari bazaga yozilmaydi — faqat suhbat davomida xotirada turadi.
"""
import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

from qon_tahlili import vision
from qon_tahlili.analyzer import analyze
from qon_tahlili.parser import from_dict, parse_text
from qon_tahlili.report import DISCLAIMER, render

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

router = Router()

EXAMPLE = (
    "<code>Gemoglobin 98\n"
    "Eritrotsitlar 3,9\n"
    "MCV 74\n"
    "Leykotsitlar 6,2\n"
    "Glyukoza 6,1\n"
    "Xolesterin 6,4\n"
    "LDL 4,2\n"
    "ALT 58\n"
    "Kreatinin 85\n"
    "Ferritin 9</code>"
)


class Form(StatesGroup):
    sex = State()
    age = State()
    results = State()


SEX_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="👨 Erkak", callback_data="sex:m"),
    InlineKeyboardButton(text="👩 Ayol", callback_data="sex:f"),
]])


@router.message(CommandStart())
@router.message(Command("yangi"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "👋 Assalomu alaykum! Men qon tahlili natijalaringizni tahlil qilib beraman:\n"
        "• qaysi ko'rsatkichlar normadan chiqqanini,\n"
        "• bu qaysi kasallik belgisi bo'lishi mumkinligini,\n"
        "• kelajakda qanday kasalliklar xavfi borligini,\n"
        "• va ularga qarshi nima qilish kerakligini aytaman.\n\n" + DISCLAIMER
    )
    await message.answer("Normalar jinsga qarab farq qiladi. Jinsingizni tanlang:", reply_markup=SEX_KB)
    await state.set_state(Form.sex)


@router.callback_query(Form.sex, F.data.startswith("sex:"))
async def choose_sex(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(sex=call.data.split(":")[1])
    await call.message.edit_text("Yoshingizni yozing (masalan: <b>35</b>):")
    await state.set_state(Form.age)
    await call.answer()


@router.message(Form.sex)
async def sex_reminder(message: Message) -> None:
    await message.answer("Iltimos, tugma orqali jinsingizni tanlang:", reply_markup=SEX_KB)


@router.message(Form.age)
async def set_age(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or not 1 <= int(text) <= 110:
        await message.answer("Yoshni raqam bilan yozing, masalan: <b>35</b>")
        return
    await state.update_data(age=int(text))
    await state.set_state(Form.results)
    photo_hint = "\n\n📷 Yoki laboratoriya blankasini <b>rasmga olib</b> yuboring." if vision.is_enabled() else ""
    await message.answer(
        "Endi tahlil natijalarini yuboring — har bir ko'rsatkich nomi va qiymati. Masalan:\n\n"
        f"{EXAMPLE}{photo_hint}"
    )


async def _send_report(message: Message, state: FSMContext, values: dict) -> None:
    if not values:
        await message.answer(
            "😕 Birorta ham ko'rsatkichni taniy olmadim. Nomi va qiymatini quyidagicha yozing:\n\n" + EXAMPLE
        )
        return
    data = await state.get_data()
    report = analyze(values, data["sex"], data.get("age"))
    for chunk in render(report):
        await message.answer(chunk)
    await message.answer("Yana tahlil yuborishingiz mumkin. Jins/yoshni o'zgartirish uchun: /yangi")


@router.message(Form.results, F.text)
async def results_text(message: Message, state: FSMContext) -> None:
    await _send_report(message, state, parse_text(message.text))


@router.message(Form.results, F.photo | F.document)
async def results_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    if not vision.is_enabled():
        await message.answer("Rasmdan o'qish hozircha yoqilmagan. Natijalarni matn ko'rinishida yozing:\n\n" + EXAMPLE)
        return
    if message.photo:
        file_id, media_type = message.photo[-1].file_id, "image/jpeg"
    elif message.document.mime_type in ("image/jpeg", "image/png", "image/webp"):
        file_id, media_type = message.document.file_id, message.document.mime_type
    else:
        await message.answer("Faqat rasm (JPG/PNG) yuboring yoki natijalarni matn ko'rinishida yozing.")
        return

    wait = await message.answer("⏳ Rasmni o'qiyapman...")
    buffer = await bot.download(file_id)
    try:
        raw = await vision.extract_from_image(buffer.read(), media_type)
    except vision.VisionUnavailable as e:
        await wait.edit_text(f"😕 {e}. Natijalarni matn ko'rinishida yozib yuboring.")
        return
    await wait.delete()
    values = from_dict(raw)
    if values:
        await message.answer("📋 Rasmdan o'qilgan qiymatlarni blankadagi bilan solishtirib chiqing — xato bo'lsa, matn bilan qayta yuboring.")
    await _send_report(message, state, values)


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Boshlash uchun /start bosing.")


async def main() -> None:
    token = os.getenv("QON_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("QON_BOT_TOKEN .env faylida topilmadi. @BotFather'dan yangi bot ochib, tokenini qo'shing.")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Qon tahlili boti ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
