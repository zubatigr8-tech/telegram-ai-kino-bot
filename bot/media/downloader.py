"""yt-dlp orqali video va qo'shiqlarni yuklab olish.

yt-dlp sinxron ishlaydi, shuning uchun uni alohida oqimda (asyncio.to_thread)
chaqiramiz — aks holda yuklash vaqtida bot boshqa foydalanuvchilarga javob bera olmaydi."""
import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from yt_dlp.cookies import YoutubeDLCookieJar
from yt_dlp.utils import DownloadError, match_filter_func

from bot.media.ffmpeg import ffmpeg_dir, has_audio, merge_audio
from shared.config import settings

logger = logging.getLogger(__name__)

# Avval alohida video + alohida ovoz (Instagram/YouTube ovozni ko'pincha alohida oqimda beradi),
# bo'lmasa — ovozi ichida bo'lgan bitta fayl. Sifat chegarasi formatda EMAS, saralashda (format_sort):
# avvalgi "height<=720" vertikal videolarni (720x1280 — Reels/Shorts/TikTok) butunlay chiqarib
# tashlab, ovozsiz zaxira variantga tushib qolardi.
VIDEO_FORMAT = "bv+ba/b"
# "res" — videoning KICHIK tomoni, ya'ni vertikal 720x1280 ham "720p" hisoblanadi
VIDEO_SORT = ["res:720", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"]
# Birinchi urinish 50 MB dan oshsa — pastroq sifat
SMALL_VIDEO_SORT = ["res:480", "vcodec:h264", "acodec:aac", "ext:mp4:m4a"]
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
    def warning(self, msg): logger.warning("yt-dlp: %s", msg)  # masalan: "cookies are no longer valid"
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
    proxy = getattr(settings, "PROXY_URL", "")
    if proxy:
        opts["proxy"] = proxy
    cookie_file = _cookie_file()
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


_env_cookie_path: str | None = None
_env_cookie_checked = False


def _json_cookies_to_lines(raw: str) -> list[str]:
    """Brauzer kengaytmasi JSON formatida eksport qilgan cookies'ni Netscape qatorlariga o'giradi."""
    try:
        data = json.loads(raw)
    except ValueError:
        logger.warning("Cookies JSON'ga o'xshaydi, lekin uni o'qib bo'lmadi — e'tiborsiz qoldirildi")
        return []
    if isinstance(data, dict):
        data = data.get("cookies") or [data]
    lines = []
    for c in data if isinstance(data, list) else []:
        if not isinstance(c, dict) or not c.get("name") or not c.get("domain"):
            continue
        domain = str(c["domain"])
        include_sub = not c.get("hostOnly", False) or domain.startswith(".")
        expires = c.get("expirationDate") or c.get("expires") or 0
        try:
            expires = int(float(expires))
        except (TypeError, ValueError):
            expires = 0
        prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        lines.append("\t".join([
            prefix + domain, "TRUE" if include_sub else "FALSE", str(c.get("path") or "/"),
            "TRUE" if c.get("secure") else "FALSE", str(max(expires, 0)),
            str(c["name"]), str(c.get("value", "")),
        ]))
    return lines


def _netscape_lines(raw: str) -> list[str]:
    """Netscape matnidan faqat to'g'ri cookie qatorlarini oladi (buzuqlarini tashlab yuboradi)."""
    lines = []
    for line in raw.replace("\\n", "\n").splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        parts = line.split("\t") if "\t" in line else line.split(None, 6)
        if len(parts) == 6:
            parts.append("")  # qiymati bo'sh cookie
        if len(parts) != 7:
            continue
        lines.append("\t".join(p.strip() for p in parts))
    return lines


def _cookie_file() -> str | None:
    """COOKIES_FILE (fayl) yoki COOKIES_TEXT* (hostingdagi o'zgaruvchilar) dan cookies fayli yo'li.

    Har qanday formatdagi xato cookies botni to'xtatmasligi kerak: JSON o'giriladi, buzuq qatorlar
    tashlanadi, fayl baribir o'qilmasa — yuklash cookies'siz davom etadi."""
    global _env_cookie_path, _env_cookie_checked
    if settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE):
        return settings.COOKIES_FILE
    if _env_cookie_checked:
        return _env_cookie_path
    _env_cookie_checked = True

    # COOKIES_TEXT, COOKIES_TEXT_INSTAGRAM, COOKIES_TEXT_YOUTUBE ... — hammasi bitta faylga qo'shiladi
    lines = []
    for name, value in sorted(os.environ.items()):
        if not name.startswith("COOKIES_TEXT") or not value.strip():
            continue
        raw = value.strip().strip('"').strip()
        found = _json_cookies_to_lines(raw) if raw.startswith(("[", "{")) else _netscape_lines(raw)
        domains = sorted({line.split("\t")[0].replace("#HttpOnly_", "").lstrip(".") for line in found})
        logger.info("%s: %d ta cookie (%s)", name, len(found), ", ".join(domains[:6]) or "—")
        lines.extend(found)
    if not lines:
        return None

    path = Path(settings.DOWNLOAD_DIR) / "cookies_from_env.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Netscape HTTP Cookie File\n" + "\n".join(lines) + "\n", encoding="utf-8")
    try:
        YoutubeDLCookieJar(str(path)).load(ignore_discard=True, ignore_expires=True)
    except Exception as exc:
        logger.warning("Cookies faylini o'qib bo'lmadi, yuklash cookies'siz davom etadi: %s", exc)
        return None
    _env_cookie_path = str(path)
    return _env_cookie_path


def _extract(opts: dict, url: str, download: bool) -> dict | None:
    """yt-dlp'ni ishga tushiradi; cookies sababli xato bo'lsa — cookies'siz yana bir marta urinadi."""
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)
    except DownloadError as exc:
        if "cookiefile" not in opts or "cookie" not in str(exc).lower():
            raise
        logger.warning("Cookies bilan xato (%s) — cookies'siz qayta urinilmoqda", exc)
        opts = {k: v for k, v in opts.items() if k != "cookiefile"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=download)


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
    # Asl xatoni logga yozamiz — hostingda (Railway → Logs) aniq sababni ko'rish uchun
    logger.warning("Yuklab bo'lmadi: %s", exc)
    text = str(exc).lower()
    if "not a bot" in text or "confirm you" in text:
        # YouTube server (hosting) IP manzillarini "bot" deb to'sadi — cookies kerak
        return MediaError(
            "YouTube vaqtincha yuklashga ruxsat bermayapti. Birozdan so'ng qayta urinib ko'ring "
            "yoki boshqa havola yuboring."
        )
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


def _download_video_sync(url: str, outdir: Path, sort: list[str]) -> VideoResult:
    opts = _base_opts(outdir)
    opts.update({
        "format": VIDEO_FORMAT,
        "format_sort": sort,
        "merge_output_format": "mp4",
        "match_filter": match_filter_func(f"duration <=? {settings.MAX_VIDEO_DURATION}"),
    })
    try:
        info = _extract(opts, url, download=True)
    except DownloadError as exc:
        raise _friendly_error(exc) from exc
    if not info:
        raise MediaError("Video juda uzun yoki yuklab bo'lmadi.")

    entry = _first_entry(info)
    path = _downloaded_path(entry)
    if path is None:
        raise MediaError("Video juda uzun yoki yuklab bo'lmadi.")
    audio_formats = sum(1 for f in entry.get("formats") or [] if f.get("acodec") not in (None, "none"))
    logger.info(
        "Yuklandi: %s | format=%s | %sx%s | video=%s | audio=%s | ovozli formatlar soni=%s | cookies=%s",
        entry.get("extractor_key"), entry.get("format_id"), entry.get("width"), entry.get("height"),
        entry.get("vcodec"), entry.get("acodec"), audio_formats, "bor" if _cookie_file() else "yo'q",
    )
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


async def _ensure_audio(url: str, result: VideoResult, outdir: Path) -> VideoResult:
    """Videoda ovoz yo'lagi bo'lmasa — audioni alohida yuklab, videoga qo'shadi."""
    if await has_audio(result.path):
        return result
    logger.warning("Video ovozsiz yuklandi, audio alohida yuklanmoqda: %s", url)
    audio_dir = outdir / "audio"
    audio_dir.mkdir(exist_ok=True)
    try:
        audio = await asyncio.to_thread(_download_audio_sync, url, audio_dir)
    except (DownloadError, MediaError) as exc:
        logger.warning("Audioni alohida yuklab bo'lmadi: %s", exc)
        return result
    if not await has_audio(audio.path):
        logger.warning("Alohida yuklangan faylda ham ovoz yo'q: %s", url)
        return result
    merged = outdir / "merged.mp4"
    if await merge_audio(result.path, audio.path, merged):
        result.path.unlink(missing_ok=True)
        result.path = merged
    return result


async def download_video(url: str, outdir: Path) -> VideoResult:
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    result = await asyncio.to_thread(_download_video_sync, url, outdir, VIDEO_SORT)
    if result.path.stat().st_size > limit:
        # Juda katta — pastroq sifatda qayta urinib ko'ramiz (katta fayl ham qo'shiqni aniqlash uchun qoladi)
        small_dir = outdir / "small"
        small_dir.mkdir(exist_ok=True)
        try:
            small = await asyncio.to_thread(_download_video_sync, url, small_dir, SMALL_VIDEO_SORT)
        except MediaError:
            small = None
        if small is not None and small.path.stat().st_size < result.path.stat().st_size:
            result.path.unlink(missing_ok=True)
            result = small
    return await _ensure_audio(url, result, outdir)


@dataclass
class SongCandidate:
    """Qidiruv natijasidagi bitta qo'shiq."""
    url: str
    title: str
    artist: str | None
    duration: float | None
    source: str  # youtube | soundcloud


def _search_sync(prefix: str, query: str, limit: int) -> list[SongCandidate]:
    opts = _base_opts(Path(settings.DOWNLOAD_DIR))
    opts.update({"extract_flat": "in_playlist", "noplaylist": False, "playlistend": limit})
    info = _extract(opts, f"{prefix}{limit}:{query}", download=False)
    source = "soundcloud" if prefix == "scsearch" else "youtube"
    result = []
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        duration = entry.get("duration") or 0
        if duration and not (20 <= duration <= MAX_SONG_DURATION):
            continue  # juda qisqa (reklama/shorts) yoki juda uzun (mix, podkast)
        url = entry.get("url") or entry.get("webpage_url")
        if not url and entry.get("id") and source == "youtube":
            url = f"https://www.youtube.com/watch?v={entry['id']}"
        if not url or not entry.get("title"):
            continue
        result.append(SongCandidate(
            url=url,
            title=entry["title"],
            artist=entry.get("uploader") or entry.get("channel"),
            duration=duration or None,
            source=source,
        ))
    return result


async def search_songs(query: str, limit: int = 6) -> list[SongCandidate]:
    """Qo'shiq nomi yoki matni (lyrics) bo'yicha qidiradi: avval YouTube, bo'lmasa SoundCloud."""
    for prefix, q in (("ytsearch", f"{query} lyrics"), ("ytsearch", query), ("scsearch", query)):
        try:
            found = await asyncio.to_thread(_search_sync, prefix, q, limit)
        except Exception as exc:  # qidiruv sahifasi to'silgan bo'lishi mumkin — keyingi manbaga o'tamiz
            logger.warning("Qidiruv xatosi (%s %s): %s", prefix, q, exc)
            continue
        if found:
            return found[:limit]
    return []


def _download_audio_sync(url: str, outdir: Path) -> AudioResult:
    opts = _base_opts(outdir)
    opts["format"] = AUDIO_FORMAT
    info = _extract(opts, url, download=True)
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


async def download_song(url: str, fallback_query: str, outdir: Path) -> AudioResult | None:
    """Audioni yuklaydi. YouTube hostingni to'sib qo'ysa — xuddi shu qo'shiqni SoundCloud'dan qidiradi."""
    try:
        return await asyncio.to_thread(_download_audio_sync, url, outdir)
    except (DownloadError, MediaError) as exc:
        logger.warning("Audio yuklanmadi (%s): %s", url, exc)
    if "soundcloud.com" in url:
        return None
    try:
        found = await asyncio.to_thread(_search_sync, "scsearch", fallback_query, 3)
        if found:
            return await asyncio.to_thread(_download_audio_sync, found[0].url, outdir)
    except Exception as exc:
        logger.warning("SoundCloud'dan ham yuklab bo'lmadi (%s): %s", fallback_query, exc)
    return None


async def find_and_download_song(query: str, outdir: Path) -> AudioResult | None:
    """Aniqlangan qo'shiqning to'liq versiyasini qidirib, audiosini yuklaydi."""
    candidates = await search_songs(query, limit=5)
    if not candidates:
        return None
    return await download_song(candidates[0].url, query, outdir)
