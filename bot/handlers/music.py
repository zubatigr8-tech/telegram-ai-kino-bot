"""Qo'shiq nomi yoki matni (lyrics) bo'yicha qidirish.

Foydalanuvchi oddiy matn yozsa (masalan, qo'shiqdan bir parcha), bot mos qo'shiqlar
ro'yxatini tugmalar bilan ko'rsatadi; tanlangan qo'shiq audio qilib yuboriladi."""
import logging
import secrets
import shutil
import tempfile
from collections import OrderedDict
from html import escape as h
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.chat_action import ChatActionSender

from bot.handlers.media import _bot_mention, _download_slots, _get_song, _limit_bytes, _save_song
from bot.media.downloader import SongCandidate, download_song, search_songs
from bot.media.links import find_urls
from shared.config import settings
from shared.db.models import SongCache

logger = logging.getLogger(__name__)
router = Router(name="music")

MIN_QUERY_LEN = 3
MAX_QUERY_LEN = 300
RESULTS = 6

# Callback'da 64 baytdan uzun ma'lumot yuborib bo'lmaydi — natijalarni qisqa kalit bilan xotirada saqlaymiz
_candidates: OrderedDict[str, SongCandidate] = OrderedDict()
_MAX_STORED = 3000
_busy_users: set[int] = set()


def _remember(candidate: SongCandidate) -> str:
    token = secrets.token_hex(5)
    _candidates[token] = candidate
    while len(_candidates) > _MAX_STORED:
        _candidates.popitem(last=False)
    return token


def _fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    return f" ({seconds // 60}:{seconds % 60:02d})"


def _is_search_text(text: str | None) -> bool:
    if not text or text.startswith("/") or find_urls(text):
        return False
    return MIN_QUERY_LEN <= len(text.strip()) <= MAX_QUERY_LEN


@router.message(F.text.func(_is_search_text))
async def search_by_text(message: Message) -> None:
    query = " ".join(message.text.split())
    status = await message.answer(f"🔎 «{h(query[:80])}» bo'yicha qo'shiq qidirilmoqda...")
    async with ChatActionSender(bot=message.bot, chat_id=message.chat.id, action=ChatAction.TYPING):
        candidates = await search_songs(query, limit=RESULTS)

    if not candidates:
        await status.edit_text(
            "😔 Hech narsa topilmadi.\n\nQo'shiq nomini, ijrochini yoki matndan boshqa parchani yozib ko'ring."
        )
        return

    lines = ["🎵 <b>Topilgan qo'shiqlar:</b>\n"]
    buttons = []
    for i, c in enumerate(candidates, start=1):
        artist = f" — {h(c.artist)}" if c.artist else ""
        lines.append(f"<b>{i}.</b> {h(c.title[:70])}{artist}{_fmt_duration(c.duration)}")
        buttons.append(InlineKeyboardButton(text=str(i), callback_data=f"song:{_remember(c)}"))
    lines.append("\n👇 Kerakli qo'shiq raqamini bosing")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons[:3], buttons[3:]] if len(buttons) > 3 else [buttons])
    await status.edit_text("\n".join(lines), reply_markup=keyboard, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("song:"))
async def send_selected_song(callback: CallbackQuery) -> None:
    candidate = _candidates.get(callback.data.split(":", 1)[1])
    if candidate is None:
        await callback.answer("Bu ro'yxat eskirgan. Qo'shiqni qaytadan qidiring.", show_alert=True)
        return
    user_id = callback.from_user.id
    if user_id in _busy_users:
        await callback.answer("⏳ Oldingi qo'shiq hali yuklanmoqda, biroz kuting.")
        return

    await callback.answer("⏳ Yuklanmoqda...")
    message = callback.message
    mention = await _bot_mention(callback.bot)
    song_key = f"src:{candidate.url}"[:512]
    caption_name = f"{candidate.artist} — {candidate.title}" if candidate.artist else candidate.title
    caption = f"🎵 <b>{h(caption_name)}</b>" + (f"\n\n📥 {mention}" if mention else "")

    cached = await _get_song(song_key)
    if cached and cached.audio_file_id:
        await message.answer_audio(cached.audio_file_id, caption=caption)
        return

    _busy_users.add(user_id)
    Path(settings.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="song_", dir=settings.DOWNLOAD_DIR))
    try:
        async with _download_slots:
            async with ChatActionSender(bot=callback.bot, chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE):
                audio = await download_song(candidate.url, caption_name, workdir)
                if audio is None:
                    await message.answer("❌ Bu qo'shiqni yuklab bo'lmadi. Ro'yxatdan boshqasini tanlab ko'ring.")
                    return
                if audio.path.stat().st_size > _limit_bytes():
                    await message.answer("❌ Qo'shiq fayli juda katta, Telegram orqali yuborib bo'lmaydi.")
                    return
                sent = await message.answer_audio(
                    FSInputFile(audio.path, filename=f"{caption_name[:60]}{audio.path.suffix}"),
                    title=candidate.title[:64],
                    performer=(candidate.artist or "")[:64] or None,
                    duration=int(audio.duration) if audio.duration else None,
                    caption=caption,
                )
        file_id = sent.audio.file_id if sent.audio else (sent.document.file_id if sent.document else None)
        await _save_song(SongCache(
            song_key=song_key, title=candidate.title[:255], artist=(candidate.artist or "")[:255] or None,
            audio_file_id=file_id, youtube_url=candidate.url if candidate.source == "youtube" else None,
        ))
    except Exception:
        logger.exception("Qo'shiqni yuborishda xatolik: %s", candidate.url)
        await message.answer("❌ Kutilmagan xatolik. Birozdan so'ng qayta urinib ko'ring.")
    finally:
        _busy_users.discard(user_id)
        shutil.rmtree(workdir, ignore_errors=True)
