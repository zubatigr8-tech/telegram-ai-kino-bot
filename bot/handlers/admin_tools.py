"""/myid — hamma uchun (ID bilish, ADMIN_IDS'ga qo'shilish uchun kerak).
Kanal chat_id'sini aniqlash (kanaldan forward) — faqat ADMIN_IDS'dagilar uchun."""
import datetime
import os
import platform

from aiogram import F, Router
from aiogram.enums import MessageOriginType
from aiogram.filters import Command
from aiogram.types import Message

from shared.config import settings

router = Router(name="admin_tools")


_STARTED_AT = datetime.datetime.now(datetime.timezone.utc)


@router.message(Command("server"), F.from_user.id.in_(settings.ADMIN_IDS))
async def server_info(message: Message) -> None:
    """Bot qayerda ishlayotganini ko'rsatadi: Railway (hosting) yoki kompyuter."""
    if os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_SERVICE_ID"):
        where = "☁️ <b>Railway hostingida</b> ishlayapti"
    else:
        where = f"🖥️ <b>Kompyuterda</b> ishlayapti ({platform.system()})"
    uptime = datetime.datetime.now(datetime.timezone.utc) - _STARTED_AT
    hours, rest = divmod(int(uptime.total_seconds()), 3600)
    await message.answer(f"{where}\n⏱ Ishga tushganiga: {hours} soat {rest // 60} daqiqa")


@router.message(Command("myid"))
async def my_id(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>")


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
