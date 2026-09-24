"""Oddiy foydalanuvchilar yuborgan rasm/matn fayllarni Claude orqali tahlil qilish."""
import io

from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.claude_client import ask_vision

router = Router(name="files")


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    photo = message.photo[-1]
    buf = io.BytesIO()
    await bot.download(photo.file_id, destination=buf)
    try:
        answer = await ask_vision(buf.getvalue(), "image/jpeg", message.caption or "")
    except RuntimeError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    except Exception:
        await message.answer("⚠️ Rasmni tahlil qilishda xatolik yuz berdi.")
        return
    await message.answer(answer)


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    doc = message.document
    name = (doc.file_name or "").lower()

    if name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        buf = io.BytesIO()
        await bot.download(doc.file_id, destination=buf)
        media_type = "image/png" if name.endswith(".png") else "image/jpeg"
        try:
            answer = await ask_vision(buf.getvalue(), media_type, message.caption or "")
        except Exception:
            await message.answer("⚠️ Faylni tahlil qilishda xatolik yuz berdi.")
            return
        await message.answer(answer)
        return

    if not name.endswith(".txt"):
        await message.answer(
            "ℹ️ Hozircha faqat rasm va matnli (.txt) fayllarni tahlil qila olaman. "
            "Boshqa formatlar (.pdf, .docx) keyinroq qo'shiladi."
        )
        return

    buf = io.BytesIO()
    await bot.download(doc.file_id, destination=buf)
    try:
        text = buf.getvalue().decode("utf-8", errors="ignore")[:6000]
    except Exception:
        await message.answer("⚠️ Faylni o'qishda xatolik yuz berdi.")
        return

    from bot.claude_client import ask_text

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
    await message.answer(answer)
