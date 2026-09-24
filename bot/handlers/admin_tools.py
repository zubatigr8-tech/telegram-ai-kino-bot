"""/myid — hamma uchun (ID bilish, ADMIN_IDS'ga qo'shilish uchun kerak).
Video/fayl file_id'sini olish, kanal chat_id'sini aniqlash — faqat ADMIN_IDS'dagilar uchun."""
from aiogram import F, Router
from aiogram.enums import MessageOriginType
from aiogram.filters import Command
from aiogram.types import Message

from shared.config import settings

router = Router(name="admin_tools")


@router.message(Command("myid"))
async def my_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


@router.message(F.video, F.from_user.id.in_(settings.ADMIN_IDS))
async def get_video_file_id(message: Message) -> None:
    await message.answer(
        "✅ Video qabul qilindi. Admin panelda kino qo'shishda shu file_id'ni ishlating:\n\n"
        f"<code>{message.video.file_id}</code>\n\n(turi: video)"
    )


@router.message(F.document, F.from_user.id.in_(settings.ADMIN_IDS))
async def get_document_file_id(message: Message) -> None:
    await message.answer(
        "✅ Fayl qabul qilindi. Admin panelda kino qo'shishda shu file_id'ni ishlating:\n\n"
        f"<code>{message.document.file_id}</code>\n\n(turi: document)"
    )


@router.message(F.forward_origin, F.from_user.id.in_(settings.ADMIN_IDS))
async def get_channel_chat_id(message: Message) -> None:
    origin = message.forward_origin
    if origin.type != MessageOriginType.CHANNEL:
        await message.answer("ℹ️ Bu xabar kanaldan forward qilinmagan.")
        return
    await message.answer(
        f"📢 Kanal: <b>{origin.chat.title}</b>\n"
        f"Chat ID: <code>{origin.chat.id}</code>\n\n"
        "Majburiy kanal qilib qo'shishda shu Chat ID'ni ishlating "
        "(/admin → 📢 Kanallar → ➕ Kanal qo'shish)."
    )
