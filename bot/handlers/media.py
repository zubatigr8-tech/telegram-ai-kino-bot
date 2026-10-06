"""Instagram / YouTube / TikTok havolasi → video + undagi qo'shiq.

Oqim:
1. Foydalanuvchi havola yuboradi.
2. Bot videoni yuklab, foydalanuvchiga yuboradi.
3. Videodagi qo'shiqni Shazam orqali aniqlaydi (topilmasa — platforma metama'lumotidan),
   YouTube'dan to'liq versiyasini topib, audio qilib yuboradi.
   Qo'shiq aniqlanmasa — videoning o'z ovozi MP3 qilib yuboriladi.

Bir xil havola va qo'shiqlar keshlanadi: qayta so'ralganda Telegram file_id orqali darhol yuboriladi."""
import asyncio
import logging
import shutil
import tempfile
from html import escape as h
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.chat_action import ChatActionSender
from sqlalchemy.exc import IntegrityError

from bot.media.downloader import MediaError, VideoResult, download_video, find_and_download_song
from bot.media.ffmpeg import has_audio, to_mp3
from bot.media.links import PLATFORM_NAMES, find_supported_url, find_urls, normalize_url
from bot.media.recognizer import Song, recognize_song, song_from_metadata
from shared.config import settings
from shared.db.database import get_session
from shared.db.models import MediaCache, SongCache

logger = logging.getLogger(__name__)
router = Router(name="media")

_download_slots = asyncio.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)
_busy_users: set[int] = set()


def _limit_bytes() -> int:
    return settings.MAX_UPLOAD_MB * 1024 * 1024


async def _bot_mention(bot: Bot) -> str:
    me = await bot.me()  # aiogram natijani keshlaydi
    return f"@{me.username}" if me.username else ""


def _song_keyboard(song: SongCache) -> InlineKeyboardMarkup | None:
    buttons = []
    if song.shazam_url:
        buttons.append(InlineKeyboardButton(text="🎧 Shazam", url=song.shazam_url))
    if song.youtube_url:
        buttons.append(InlineKeyboardButton(text="▶️ YouTube", url=song.youtube_url))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


def _song_caption(song: SongCache, mention: str) -> str:
    name = f"{song.artist} — {song.title}" if song.artist else song.title
    caption = f"🎵 <b>{h(name)}</b>"
    return f"{caption}\n\n📥 {mention}" if mention else caption


def _video_caption(title: str | None, platform: str, mention: str) -> str:
    lines = []
    if title:
        short = title.strip().split("\n")[0]
        if len(short) > 200:
            short = short[:200] + "…"
        lines.append(f"🎬 {h(short)}")
    footer = f"📥 {PLATFORM_NAMES.get(platform, '')}"
    if mention:
        footer += f" • {mention}"
    lines.append(footer)
    return "\n\n".join(lines)


# ---------- Kesh ----------

async def _get_media(url_key: str) -> MediaCache | None:
    async with get_session() as session:
        return await session.get(MediaCache, url_key)


async def _get_song(song_key: str) -> SongCache | None:
    async with get_session() as session:
        return await session.get(SongCache, song_key)


async def _save_media(url_key: str, platform: str, title: str | None,
                      video_file_id: str | None, song_key: str | None) -> None:
    async with get_session() as session:
        row = await session.get(MediaCache, url_key)
        if row is None:
            session.add(MediaCache(
                url_key=url_key, platform=platform, title=(title or "")[:255] or None,
                video_file_id=video_file_id, song_key=song_key,
            ))
        else:
            row.video_file_id = video_file_id or row.video_file_id
            row.song_key = song_key or row.song_key
            row.requests += 1
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()


async def _bump_media(url_key: str) -> None:
    async with get_session() as session:
        row = await session.get(MediaCache, url_key)
        if row:
            row.requests += 1
            await session.commit()


async def _save_song(row: SongCache) -> None:
    async with get_session() as session:
        await session.merge(row)
        await session.commit()


# ---------- Qo'shiq ----------

async def _send_song(message: Message, song_row: SongCache, mention: str) -> bool:
    if not song_row.audio_file_id:
        return False
    await message.answer_audio(
        song_row.audio_file_id,
        caption=_song_caption(song_row, mention),
        reply_markup=_song_keyboard(song_row),
    )
    return True


async def _deliver_song(message: Message, song: Song, workdir: Path, mention: str) -> bool:
    """Aniqlangan qo'shiqni keshdan yoki YouTube'dan topib yuboradi."""
    cached = await _get_song(song.key)
    if cached and await _send_song(message, cached, mention):
        return True

    row = cached or SongCache(song_key=song.key, title=song.title[:255], artist=(song.artist or "")[:255] or None)
    row.shazam_url = row.shazam_url or song.shazam_url

    async with ChatActionSender(bot=message.bot, chat_id=message.chat.id, action=ChatAction.UPLOAD_VOICE):
        audio = await find_and_download_song(song.query, workdir / "song")
        if audio is None or audio.path.stat().st_size > _limit_bytes():
            await _save_song(row)
            return False
        row.youtube_url = audio.webpage_url
        sent = await message.answer_audio(
            FSInputFile(audio.path, filename=f"{song.query[:60]}{audio.path.suffix}"),
            title=song.title[:64],
            performer=(song.artist or "")[:64] or None,
            duration=int(audio.duration) if audio.duration else None,
            caption=_song_caption(row, mention),
            reply_markup=_song_keyboard(row),
        )
    if sent.audio:
        row.audio_file_id = sent.audio.file_id
    elif sent.document:
        row.audio_file_id = sent.document.file_id
    await _save_song(row)
    return True


async def _send_original_audio(message: Message, video: VideoResult, workdir: Path, mention: str) -> None:
    """Qo'shiq aniqlanmadi — videoning o'z ovozini MP3 qilib yuboramiz."""
    mp3 = workdir / "audio.mp3"
    if not await to_mp3(video.path, mp3, title=video.title):
        await message.answer("🎵 Bu videoda qo'shiq aniqlanmadi.")
        return
    if mp3.stat().st_size > _limit_bytes():
        await message.answer("🎵 Bu videoda qo'shiq aniqlanmadi.")
        return
    title = (video.title or "Audio").split("\n")[0][:60]
    caption = "🎵 Qo'shiq nomi aniqlanmadi — videodagi ovozni yubordim."
    if mention:
        caption += f"\n\n📥 {mention}"
    await message.answer_audio(
        FSInputFile(mp3, filename=f"{title}.mp3"),
        title=title,
        duration=int(video.duration) if video.duration else None,
        caption=caption,
    )


# ---------- Asosiy handler ----------

async def _process(message: Message, url: str, platform: str, status: Message) -> None:
    bot = message.bot
    mention = await _bot_mention(bot)
    # "v2:" — ovoz muammosi tuzatilgunga qadar keshlangan (ovozsiz bo'lishi mumkin) videolar qayta ishlatilmasin
    url_key = "v2:" + normalize_url(url)

    # 1) Kesh: bu havola avval yuklangan bo'lsa — darhol yuboramiz
    cached = await _get_media(url_key)
    if cached and cached.video_file_id:
        await message.answer_video(cached.video_file_id, caption=_video_caption(cached.title, platform, mention))
        await _bump_media(url_key)
        song_row = await _get_song(cached.song_key) if cached.song_key else None
        if song_row and await _send_song(message, song_row, mention):
            await _delete_quietly(status)
            return
        # Qo'shiq keshda yo'q — videoni qayta yuklab, aniqlashga harakat qilamiz (quyida)

    Path(settings.DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="dl_", dir=settings.DOWNLOAD_DIR))
    try:
        if _download_slots.locked():
            await _set_status(status, "⏳ Navbatdasiz, hozir boshqa videolar yuklanmoqda...")
        async with _download_slots:
            await _set_status(status, "⏳ Video yuklanmoqda...")
            async with ChatActionSender(bot=bot, chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO):
                video = await download_video(url, workdir)

                video_file_id = cached.video_file_id if cached else None
                if video_file_id is None:
                    if video.path.stat().st_size <= _limit_bytes():
                        caption = _video_caption(video.title, platform, mention)
                        if not await has_audio(video.path):
                            caption += "\n\n🔇 Platforma bu videoni serverga ovozsiz berdi."
                        sent = await message.answer_video(
                            FSInputFile(video.path),
                            caption=caption,
                            duration=int(video.duration) if video.duration else None,
                            width=video.width,
                            height=video.height,
                            supports_streaming=True,
                        )
                        video_file_id = sent.video.file_id if sent.video else None
                    else:
                        await message.answer(
                            f"⚠️ Video hajmi {settings.MAX_UPLOAD_MB} MB dan katta, Telegram orqali "
                            "yuborib bo'lmaydi. Lekin qo'shig'ini topib beraman 👇"
                        )

            # 2) Qo'shiqni aniqlash
            await _set_status(status, "🎵 Videodagi qo'shiq aniqlanmoqda...")
            song = await recognize_song(video.path, video.duration)
            if song is None:
                song = song_from_metadata(video.meta_track, video.meta_artist)

            delivered = False
            if song is not None:
                await _set_status(status, f"🎵 Topildi: <b>{h(song.query)}</b>\n⏳ Qo'shiq yuklanmoqda...")
                delivered = await _deliver_song(message, song, workdir, mention)
                if not delivered:
                    await message.answer(
                        f"🎵 Qo'shiq: <b>{h(song.query)}</b>\n\n"
                        "To'liq versiyasini yuklab bo'lmadi, videodagi parchasini yuboraman 👇"
                    )
            if not delivered:
                await _send_original_audio(message, video, workdir, mention)

        await _save_media(url_key, platform, video.title, video_file_id, song.key if song else None)
        await _delete_quietly(status)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.message(F.text.func(lambda text: find_supported_url(text) is not None))
async def handle_media_link(message: Message) -> None:
    url, platform = find_supported_url(message.text)
    user_id = message.from_user.id

    if user_id in _busy_users:
        await message.answer("⏳ Oldingi havolangiz hali ishlanmoqda, biroz kuting.")
        return

    _busy_users.add(user_id)
    status = await message.answer(f"🔎 {PLATFORM_NAMES[platform]} havolasi qabul qilindi...")
    try:
        await _process(message, url, platform, status)
    except MediaError as exc:
        await _safe_edit(status, f"❌ {h(str(exc))}")
    except Exception:
        logger.exception("Havolani ishlashda xatolik: %s", url)
        await _safe_edit(status, "❌ Kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
    finally:
        _busy_users.discard(user_id)


@router.message(F.text.func(lambda text: bool(find_urls(text))))
async def unsupported_link(message: Message) -> None:
    await message.answer(
        "❌ Bu havola qo'llab-quvvatlanmaydi.\n\n"
        "Faqat <b>Instagram</b>, <b>YouTube</b> va <b>TikTok</b> havolalarini yuboring."
    )


async def _set_status(status: Message, text: str) -> None:
    try:
        await status.edit_text(text)
    except Exception:
        pass  # holat xabari o'chirilgan yoki matn o'zgarmagan — muhim emas


async def _delete_quietly(status: Message) -> None:
    try:
        await status.delete()
    except Exception:
        pass


async def _safe_edit(status: Message, text: str) -> None:
    try:
        await status.edit_text(text)
    except Exception:
        await status.answer(text)
