"""ffmpeg'ni topish va audio bilan ishlash.

Serverda ffmpeg o'rnatilgan bo'lsa o'shani ishlatamiz, bo'lmasa `imageio-ffmpeg`
paketi bilan keladigan tayyor ffmpeg'dan foydalanamiz — shunda hostingda (Railway,
Render) alohida ffmpeg o'rnatish shart emas."""
import asyncio
import logging
import os
import shutil
from functools import lru_cache
from pathlib import Path

from shared.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


@lru_cache(maxsize=1)
def ffmpeg_dir() -> str:
    """yt-dlp'ga beriladigan papka: unda aynan `ffmpeg` nomli fayl bo'lishi kerak
    (imageio-ffmpeg faylining nomi `ffmpeg-linux-x86_64-v7...` bo'lgani uchun yorliq yaratamiz)."""
    exe = Path(ffmpeg_exe())
    if exe.stem == "ffmpeg":
        return str(exe.parent)
    bin_dir = Path(settings.DOWNLOAD_DIR) / ".bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not link.exists():
        try:
            link.symlink_to(exe)
        except OSError:
            shutil.copy2(exe, link)  # Windows'da symlink uchun ruxsat bo'lmasligi mumkin
    return str(bin_dir)


async def run_ffmpeg(*args: str, timeout: float = 180) -> bool:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("ffmpeg vaqt limitidan oshdi: %s", args)
        return False
    if proc.returncode != 0:
        logger.warning("ffmpeg xatosi (%s): %s", proc.returncode, stderr.decode(errors="ignore")[-500:])
        return False
    return True


async def extract_clip(src: Path, dst: Path, start: float, duration: float = 15) -> bool:
    """Videodan qo'shiqni aniqlash uchun qisqa mono WAV parcha kesib oladi."""
    return await run_ffmpeg(
        "-ss", f"{max(start, 0):.2f}", "-t", f"{duration:.2f}", "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dst),
        timeout=60,
    ) and dst.exists() and dst.stat().st_size > 1000


async def to_mp3(src: Path, dst: Path, title: str | None = None, artist: str | None = None) -> bool:
    args = ["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "192k"]
    if title:
        args += ["-metadata", f"title={title}"]
    if artist:
        args += ["-metadata", f"artist={artist}"]
    args.append(str(dst))
    return await run_ffmpeg(*args, timeout=300) and dst.exists() and dst.stat().st_size > 1000
