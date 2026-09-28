"""Videodagi qo'shiqni aniqlash (Shazam) — API kalit talab qilinmaydi."""
import logging
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from bot.media.ffmpeg import extract_clip

logger = logging.getLogger(__name__)

try:
    with warnings.catch_warnings():
        # shazamio ichidagi pydub ffmpeg'ni PATH'dan topa olmasa ogohlantiradi — bizga pydub kerak emas
        warnings.simplefilter("ignore", RuntimeWarning)
        from shazamio import Shazam
except ImportError:
    # shazamio'ning tayyor paketi faqat Python 3.9–3.12 uchun chiqarilgan. Yangiroq Python'da
    # bot baribir ishlaydi: qo'shiq nomi platforma metama'lumotidan olinadi.
    Shazam = None
    logger.warning("shazamio o'rnatilmagan — qo'shiqni Shazam orqali aniqlash o'chirilgan (Python 3.12 tavsiya etiladi)")

CLIP_SECONDS = 15

# TikTok/Instagram'da muallifning o'z ovozi shunday nomlanadi — bu haqiqiy qo'shiq emas
_ORIGINAL_SOUND_RE = re.compile(
    r"original\s+(sound|audio)|оригинальный\s+звук|son\s+original|sonido\s+original|orijinal\s+ses|asl\s+ovoz",
    re.IGNORECASE,
)


@dataclass
class Song:
    title: str
    artist: str | None
    shazam_url: str | None = None
    cover_url: str | None = None

    @property
    def key(self) -> str:
        return f"{self.artist or ''} - {self.title}".strip(" -").lower()[:512]

    @property
    def query(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


def _clip_offsets(duration: float | None) -> list[float]:
    # Avval boshidan, keyin o'rtasidan (qo'shiq ko'pincha gapdan keyin boshlanadi), so'ng oxiriga yaqin
    if not duration or duration <= CLIP_SECONDS + 5:
        return [0]
    offsets = [0, max(duration / 2 - CLIP_SECONDS / 2, 0)]
    if duration > 60:
        offsets.append(duration - CLIP_SECONDS - 5)
    return offsets


async def recognize_song(video_path: Path, duration: float | None) -> Song | None:
    if Shazam is None:
        return None
    shazam = Shazam()
    for i, offset in enumerate(_clip_offsets(duration)):
        clip = video_path.with_name(f"clip_{i}.wav")
        if not await extract_clip(video_path, clip, offset, CLIP_SECONDS):
            if i == 0:
                return None  # videoda ovoz yo'lagi yo'q
            continue
        try:
            result = await shazam.recognize(clip.read_bytes())
        except Exception:
            logger.warning("Shazam so'rovi muvaffaqiyatsiz", exc_info=True)
            continue
        finally:
            clip.unlink(missing_ok=True)

        track = (result or {}).get("track")
        if track and track.get("title"):
            return Song(
                title=track["title"],
                artist=track.get("subtitle"),
                shazam_url=track.get("url"),
                cover_url=(track.get("images") or {}).get("coverarthq") or (track.get("images") or {}).get("coverart"),
            )
    return None


def song_from_metadata(track: str | None, artist: str | None) -> Song | None:
    """Shazam topa olmasa — platforma ko'rsatgan qo'shiq nomi (agar "original sound" bo'lmasa)."""
    if not track or _ORIGINAL_SOUND_RE.search(track):
        return None
    return Song(title=track.strip(), artist=(artist or "").strip() or None)
