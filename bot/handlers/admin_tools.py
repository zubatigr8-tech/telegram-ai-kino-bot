"""/myid — hamma uchun (ID bilish, ADMIN_IDS'ga qo'shilish uchun kerak).
Kanal chat_id'sini aniqlash (kanaldan forward) — faqat ADMIN_IDS'dagilar uchun."""
import datetime
from html import escape as h
import os
import platform

from aiogram import F, Router
from aiogram.enums import MessageOriginType
from aiogram.filters import Command
from aiogram.types import Message

from bot.media.downloader import clear_uploaded_cookies, cookie_status, save_uploaded_cookies
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


COOKIES_HELP = (
    "🍪 <b>Cookies yuklash</b>\n\n"
    "1. Chrome'da Instagram (yoki YouTube) akkauntingizga kiring.\n"
    "2. 🧩 → <b>Get cookies.txt LOCALLY</b> → <b>Export</b> (format: Netscape yoki JSON — farqi yo'q).\n"
    "3. Yuklangan <code>.txt</code> / <code>.json</code> faylni shu botga <b>fayl qilib</b> yuboring.\n\n"
    "/cookies — holat, /cookies_clear — yuklangan cookies'ni o'chirish"
)


@router.message(Command("cookies"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cookies_info(message: Message) -> None:
    status = cookie_status()
    if not status:
        await message.answer("🍪 Hozircha cookies yo'q.\n\n" + COOKIES_HELP)
        return
    lines = [
        f"• <b>{h(name)}</b>: {count} ta ({h(', '.join(domains[:5])) or '—'})"
        for name, count, domains in status
    ]
    await message.answer("🍪 <b>Cookies manbalari:</b>\n" + "\n".join(lines) + "\n\n" + COOKIES_HELP)


@router.message(Command("cookies_clear"), F.from_user.id.in_(settings.ADMIN_IDS))
async def cookies_clear(message: Message) -> None:
    removed = clear_uploaded_cookies()
    await message.answer(f"🗑 Botga yuklangan {removed} ta cookies fayli o'chirildi.")


@router.message(
    F.document, F.from_user.id.in_(settings.ADMIN_IDS),
    F.document.func(lambda doc: (doc.file_name or "").lower().endswith((".txt", ".json"))),
)
async def cookies_upload(message: Message) -> None:
    if message.document.file_size and message.document.file_size > 2 * 1024 * 1024:
        await message.answer("❌ Fayl juda katta (2 MB dan oshmasligi kerak).")
        return
    buffer = await message.bot.download(message.document)
    raw = buffer.read().decode("utf-8", errors="ignore")
    count, domains = save_uploaded_cookies(raw)
    if not count:
        await message.answer("❌ Bu faylda cookie topilmadi.\n\n" + COOKIES_HELP)
        return
    await message.answer(
        f"✅ <b>{count} ta cookie saqlandi</b>\n"
        f"Saytlar: {h(', '.join(domains[:8]))}\n\n"
        "Endi havolani qayta yuborib ko'ring. Xavfsizlik uchun yuqoridagi fayl xabarini o'chirib qo'ying."
    )


@router.message(Command("admin", "server", "cookies", "cookies_clear"))
async def not_admin(message: Message) -> None:
    # Adminlar uchun /admin va /server yuqoridagi handlerlarda ishlaydi; bu yerga faqat
    # ADMIN_IDS'da yo'q foydalanuvchi tushadi — unga sababini tushuntiramiz
    await message.answer(
        "⛔️ Bu buyruq faqat adminlar uchun.\n\n"
        f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>\n\n"
        "Agar bot egasi siz bo'lsangiz — hostingdagi <b>ADMIN_IDS</b> sozlamasiga shu raqamni yozing."
    )


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
