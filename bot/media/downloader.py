"""yt-dlp orqali video va qo'shiqlarni yuklab olish.

yt-dlp sinxron ishlaydi, shuning uchun uni alohida oqimda (asyncio.to_thread)
chaqiramiz — aks holda yuklash vaqtida bot boshqa foydalanuvchilarga javob bera olmaydi."""
import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from yt_dlp.utils import DownloadError, match_filter_func

from bot.media.ffmpeg import ffmpeg_dir
from shared.config import settings

logger = logging.getLogger(__name__)

# 720p gacha, Telegram'da to'g'ridan-to'g'ri o'ynaydigan mp4 (h264 + aac)
VIDEO_FORMAT = (
    "bv*[height<=720][ext=mp4][vcodec^=avc]+ba[ext=m4a]"
    "/b[height<=720][ext=mp4]"
    "/bv*[height<=720]+ba"
    "/b[height<=720]/b"
)
# Birinchi urinish 50 MB dan oshsa — pastroq sifat
SMALL_VIDEO_FORMAT = "b[height<=480][ext=mp4]/bv*[height<=480]+ba/b[height<=480]/worst"
AUDIO_FORMAT = "ba[ext=m4a]/ba[ext=mp3]/ba/b"
MAX_SONG_DURATION = 15 * 60


class MediaError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


@dataclass
class VideoResult:
    path: Path
    title: str | None
    duration: float | None
    width: int | None
    height: int | None
    webpage_url: str | None
    # Platforma o'zi ko'rsatgan qo'shiq (TikTok/Instagram/YouTube Music metama'lumoti)
    meta_track: str | None
    meta_artist: str | None


@dataclass
class AudioResult:
    path: Path
    title: str | None
    artist: str | None
    duration: float | None
    webpage_url: str | None


class _QuietLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): logger.debug("yt-dlp: %s", msg)
    def error(self, msg): logger.info("yt-dlp: %s", msg)


def _base_opts(outdir: Path) -> dict:
    opts = {
        "outtmpl": str(outdir / "%(id).60s.%(ext)s"),
        "noplaylist": True,
        "playlistend": 1,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _QuietLogger(),
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "ffmpeg_location": ffmpeg_dir(),
        "restrictfilenames": True,
        "http_headers": {"Accept-Language": "en-US,en;q=0.9"},
    }
    if settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE):
        opts["cookiefile"] = settings.COOKIES_FILE
    return opts


def _first_entry(info: dict) -> dict:
    # Instagram karusel yoki pleylist bo'lsa — birinchi elementni olamiz
    entries = info.get("entries")
    if entries:
        for entry in entries:
            if entry:
                return entry
        raise MediaError("Havolada video topilmadi.")
    return info


def _downloaded_path(info: dict) -> Path | None:
    for item in info.get("requested_downloads") or []:
        path = item.get("filepath")
        if path and os.path.exists(path):
            return Path(path)
    path = info.get("filepath") or info.get("_filename")
    if path and os.path.exists(path):
        return Path(path)
    return None


def _friendly_error(exc: Exception) -> MediaError:
    text = str(exc).lower()
    if "private" in text or "login" in text or "sign in" in text or "cookies" in text:
        return MediaError("Bu video yopiq (private) yoki kirish talab qiladi — yuklab bo'lmadi.")
    if "unavailable" in text or "not available" in text or "removed" in text or "404" in text:
        return MediaError("Video topilmadi yoki o'chirilgan.")
    if "duration" in text or "does not pass filter" in text:
        minutes = settings.MAX_VIDEO_DURATION // 60
        return MediaError(f"Video juda uzun. {minutes} daqiqagacha bo'lgan videolarni yuklay olaman.")
    if "no video formats" in text or "no formats" in text:
        return MediaError("Havolada video topilmadi (ehtimol bu rasm yoki matnli post).")
    return MediaError("Videoni yuklab bo'lmadi. Havolani tekshirib, qaytadan urinib ko'ring.")


def _download_video_sync(url: str, outdir: Path, fmt: str) -> VideoResult:
    opts = _base_opts(outdir)
    opts.update({
        "format": fmt,
        "merge_output_format": "mp4",
        "match_filter": match_filter_func(f"duration <=? {settings.MAX_VIDEO_DURATION}"),
    })
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except DownloadError as exc:
        raise _friendly_error(exc) from exc
    if not info:
        raise MediaError("Video juda uzun yoki yuklab bo'lmadi.")

    entry = _first_entry(info)
    path = _downloaded_path(entry)
    if path is None:
        raise MediaError("Video juda uzun yoki yuklab bo'lmadi.")
    return VideoResult(
        path=path,
        title=entry.get("title") or entry.get("description"),
        duration=entry.get("duration"),
        width=entry.get("width"),
        height=entry.get("height"),
        webpage_url=entry.get("webpage_url") or url,
        meta_track=entry.get("track"),
        meta_artist=(entry.get("artist") or entry.get("creator")) if entry.get("track") else None,
    )


async def download_video(url: str, outdir: Path) -> VideoResult:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    result = await asyncio.to_thread(_download_video_sync, url, outdir, VIDEO_FORMAT)
    if result.path.stat().st_size <= limit:
        return result

    # Juda katta — pastroq sifatda qayta urinib ko'ramiz (katta fayl ham qo'shiqni aniqlash uchun qoladi)
    small_dir = outdir / "small"
    small_dir.mkdir(exist_ok=True)
    try:
        small = await asyncio.to_thread(_download_video_sync, url, small_dir, SMALL_VIDEO_FORMAT)
    except MediaError:
        return result
    if small.path.stat().st_size < result.path.stat().st_size:
        result.path.unlink(missing_ok=True)
        return small
    return result


def _search_song_sync(query: str) -> dict | None:
    opts = _base_opts(Path(settings.DOWNLOAD_DIR))
    opts.update({"extract_flat": "in_playlist", "noplaylist": False, "playlistend": 5})
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        duration = entry.get("duration") or 0
        if 0 < duration <= MAX_SONG_DURATION:
            return entry
    return None


def _download_audio_sync(url: str, outdir: Path) -> AudioResult:
    opts = _base_opts(outdir)
    opts["format"] = AUDIO_FORMAT
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    entry = _first_entry(info)
    path = _downloaded_path(entry)
    if path is None:
        raise MediaError("Qo'shiqni yuklab bo'lmadi.")
    return AudioResult(
        path=path,
        title=entry.get("track") or entry.get("title"),
        artist=entry.get("artist") or entry.get("uploader"),
        duration=entry.get("duration"),
        webpage_url=entry.get("webpage_url") or url,
    )


async def find_and_download_song(query: str, outdir: Path) -> AudioResult | None:
    """YouTube'dan qo'shiqning to'liq versiyasini qidirib, audiosini yuklaydi."""
    try:
        entry = await asyncio.to_thread(_search_song_sync, query)
        if entry is None:
            return None
        url = entry.get("url") or f"https://www.youtube.com/watch?v={entry['id']}"
        return await asyncio.to_thread(_download_audio_sync, url, outdir)
    except (DownloadError, MediaError) as exc:
        logger.info("Qo'shiqni yuklab bo'lmadi (%s): %s", query, exc)
        return None
