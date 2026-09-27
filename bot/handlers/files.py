"""Oddiy foydalanuvchilar yuborgan rasm/matn fayllarni Claude orqali tahlil qilish."""
import io

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message

from bot.claude_client import ask_text, ask_vision
from bot.utils import answer_plain

router = Router(name="files")

# Telegram Bot API botga 20 MB dan katta faylni yuklab olishga ruxsat bermaydi
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
MAX_TEXT_FILE_BYTES = 1024 * 1024
MAX_TEXT_CHARS = 6000

IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


async def _download(bot: Bot, file_id: str) -> bytes:
    buf = io.BytesIO()
    await bot.download(file_id, destination=buf)
    return buf.getvalue()


async def _analyze_image(message: Message, bot: Bot, file_id: str, media_type: str) -> None:
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        data = await _download(bot, file_id)
        answer = await ask_vision(data, media_type, message.caption or "")
    except RuntimeError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    except Exception:
        await message.answer("⚠️ Rasmni tahlil qilishda xatolik yuz berdi.")
        return
    await answer_plain(message, answer)


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    await _analyze_image(message, bot, message.photo[-1].file_id, "image/jpeg")


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    doc = message.document
    name = (doc.file_name or "").lower()
    ext = name[name.rfind("."):] if "." in name else ""

    if doc.file_size and doc.file_size > MAX_DOWNLOAD_BYTES:
        await message.answer("⚠️ Fayl juda katta (20 MB dan oshmasligi kerak).")
        return

    if ext in IMAGE_TYPES:
        await _analyze_image(message, bot, doc.file_id, IMAGE_TYPES[ext])
        return

    if ext != ".txt":
        await message.answer(
            "ℹ️ Hozircha faqat rasm va matnli (.txt) fayllarni tahlil qila olaman. "
            "Boshqa formatlar (.pdf, .docx) keyinroq qo'shiladi."
        )
        return

    if doc.file_size and doc.file_size > MAX_TEXT_FILE_BYTES:
        await message.answer("⚠️ Matnli fayl juda katta (1 MB dan oshmasligi kerak).")
        return

    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        text = (await _download(bot, doc.file_id)).decode("utf-8", errors="ignore")[:MAX_TEXT_CHARS]
    except Exception:
        await message.answer("⚠️ Faylni o'qishda xatolik yuz berdi.")
        return

    if not text.strip():
        await message.answer("⚠️ Fayl bo'sh yoki uning matnini o'qib bo'lmadi.")
        return

    question = message.caption or "Shu matn haqida qisqacha ma'lumot bering."
    try:
        answer = await ask_text(
            [{"role": "user", "content": f"Fayl matni:\n\n{text}\n\nSavol: {question}"}]
        )
    except RuntimeError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    except Exception:
        await message.answer("⚠️ Tahlil qilishda xatolik yuz berdi.")
        return
    await answer_plain(message, answer)
