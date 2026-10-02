"""ffmpeg/ffprobe bilan ishlash: video ma'lumotlarini o'qish, filtrlar zanjiri, kodlash."""
import asyncio
import json
import logging
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Awaitable, Callable

from video_enhancer_bot.config import settings

logger = logging.getLogger(__name__)

# progress(0.0..1.0) — ishlov berish qayergacha kelganini bildiradi
ProgressCallback = Callable[[float], Awaitable[None]]

AUDIO_BITRATE_KBPS = 192


class MediaError(Exception):
    """Foydalanuvchiga ko'rsatsa bo'ladigan xatolik."""


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    fps: str  # ffmpeg'ga to'g'ridan-to'g'ri beriladigan kasr, masalan "30000/1001"
    has_audio: bool
    # Asl videoning rang matritsasi (scale filtri uchun): "bt709" yoki "bt601"
    color_matrix: str = "bt709"

    @property
    def fps_float(self) -> float:
        return float(Fraction(self.fps))


@dataclass
class Preset:
    """Rang va tiniqlik sozlamalari. Qiymatlar "eski kino" uchun tanlangan."""
    key: str
    title: str
    saturation: float
    contrast: float
    brightness: float
    gamma: float
    vibrance: float
    sharpen: float  # cas filtri kuchi, 0..1
    denoise: str  # hqdn3d parametrlari


PRESETS: dict[str, Preset] = {
    # gamma > 1 — o'rta tonlarni yoritadi (gamma < 1 videoni qoraytirib yuborardi)
    "auto": Preset("auto", "✨ Avtomatik (tavsiya)", 1.35, 1.06, 0.03, 1.06, 0.30, 0.75, "3:2:4:3"),
    "vivid": Preset("vivid", "🌈 Juda yorqin ranglar", 1.70, 1.10, 0.04, 1.08, 0.50, 0.85, "3:2:4:3"),
    "natural": Preset("natural", "🎞 Tabiiy (faqat tiniqlik)", 1.10, 1.04, 0.01, 1.03, 0.10, 0.70, "2:1.5:3:2.5"),
}


async def _run(args: list[str], timeout: float | None = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


async def probe(path: Path) -> VideoInfo:
    code, out, err = await _run(
        [settings.FFPROBE_BIN, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        timeout=60,
    )
    if code != 0:
        logger.warning("ffprobe xatosi: %s", err[-500:])
        raise MediaError("Bu faylni video sifatida o'qib bo'lmadi.")
    data = json.loads(out)
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("Faylda video oqimi topilmadi.")
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))

    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
    fps = video.get("avg_frame_rate") or video.get("r_frame_rate") or "25/1"
    if fps in {"0/0", "0/1"}:
        fps = video.get("r_frame_rate") or "25/1"
    if Fraction(fps) > 60:  # noto'g'ri yozilgan metadata (masalan 90000/1)
        fps = "30/1"

    width, height = int(video["width"]), int(video["height"])
    # Telefonda vertikal olingan videolarda burilish metadata'da bo'ladi
    rotation = 0
    for side in video.get("side_data_list", []) or []:
        if "rotation" in side:
            rotation = abs(int(side["rotation"]))
    if rotation in {90, 270}:
        width, height = height, width
    # Rang matritsasi belgilanmagan bo'lsa, pleyerlar kabi taxmin qilamiz: HD → bt709, SD → bt601
    space = video.get("color_space") or ""
    if space == "bt709":
        matrix = "bt709"
    elif space in {"smpte170m", "bt470bg", "bt601"}:
        matrix = "bt601"
    else:
        matrix = "bt709" if min(width, height) >= 720 else "bt601"
    return VideoInfo(width, height, duration, fps, has_audio, matrix)


def target_size(info: VideoInfo) -> tuple[int, int]:
    """Natijaviy o'lcham: qisqa tomoni TARGET_HEIGHT ga tenglashtiriladi (kichraytirilmaydi)."""
    short_side = min(info.width, info.height)
    if short_side >= settings.TARGET_HEIGHT:
        w, h = info.width, info.height
    else:
        k = settings.TARGET_HEIGHT / short_side
        w, h = info.width * k, info.height * k
    # libx264 yuv420p uchun o'lchamlar juft bo'lishi shart
    return int(round(w / 2)) * 2, int(round(h / 2)) * 2


def cleanup_filters(preset: Preset) -> list[str]:
    """Kattalashtirishdan OLDIN: interleysni olib tashlash va shovqinni tozalash."""
    return [
        "bwdif=mode=send_frame:deint=interlaced",  # faqat interleysli kadrlarga ta'sir qiladi
        f"hqdn3d={preset.denoise}",
    ]


def finish_filters(preset: Preset, size: tuple[int, int] | None, in_matrix: str = "bt709") -> list[str]:
    """Kattalashtirish (kerak bo'lsa), rang, kontrast va tiniqlik.

    Natija har doim BT.709 ga o'tkaziladi va shunday belgilanadi — aks holda pleyerlar ranglarni
    noto'g'ri (sarg'ish/qizg'ish) ko'rsatadi."""
    dims = f"{size[0]}:{size[1]}:flags=lanczos:" if size else ""
    filters = [f"scale={dims}in_color_matrix={in_matrix}:out_color_matrix=bt709"]
    filters += [
        "deband=1thr=0.015:2thr=0.015:3thr=0.015:range=16",  # eski siqilgan videodagi "zinapoya" gradientlar
        f"eq=contrast={preset.contrast}:brightness={preset.brightness}"
        f":saturation={preset.saturation}:gamma={preset.gamma}",
    ]
    if preset.vibrance:
        filters.append(f"vibrance=intensity={preset.vibrance}")
    filters += [f"cas=strength={preset.sharpen}", "format=yuv420p"]
    return filters


def encode_args(info: VideoInfo, bitrate_scale: float = 1.0) -> list[str]:
    """H.264 kodlash parametrlari — natija Telegram yuborish limitiga sig'adigan qilib."""
    budget_kbps = settings.upload_limit_bytes * 8 * 0.92 / 1000 / max(info.duration, 1)
    video_kbps = int((budget_kbps - (AUDIO_BITRATE_KBPS if info.has_audio else 0)) * bitrate_scale)
    video_kbps = max(video_kbps, 300)
    args = [
        "-c:v", "libx264", "-preset", settings.X264_PRESET, "-crf", "17",
        "-threads", str(settings.FFMPEG_THREADS), "-x264-params", "rc-lookahead=20",
        "-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps * 2}k",
        "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
    ]
    if info.has_audio:
        args += ["-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_KBPS}k"]
    return args


async def run_ffmpeg(
    args: list[str], duration: float, on_progress: ProgressCallback | None = None, timeout: float | None = None
) -> None:
    """ffmpeg'ni ishga tushiradi va `-progress` chiqishidan foizni hisoblab boradi."""
    cmd = [settings.FFMPEG_BIN, "-hide_banner", "-y", "-nostats", "-progress", "pipe:1",
           "-filter_threads", str(settings.FFMPEG_THREADS), *args]
    logger.info("ffmpeg: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stderr_tail: list[str] = []

    async def read_stderr() -> None:
        assert proc.stderr
        async for line in proc.stderr:
            stderr_tail.append(line.decode(errors="replace"))
            del stderr_tail[:-30]

    async def read_progress() -> None:
        assert proc.stdout
        async for raw in proc.stdout:
            key, _, value = raw.decode(errors="replace").strip().partition("=")
            if key == "out_time_us" and value.isdigit() and duration > 0 and on_progress:
                await on_progress(min(int(value) / 1_000_000 / duration, 1.0))

    try:
        await asyncio.wait_for(asyncio.gather(read_stderr(), read_progress(), proc.wait()), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0:
        if proc.returncode in (-9, 137):
            logger.error("ffmpeg tizim tomonidan o'ldirildi — xotira yetmadi (FFMPEG_THREADS yoki TARGET_HEIGHT'ni kamaytiring)")
        logger.error("ffmpeg xatosi (%s):\n%s", proc.returncode, "".join(stderr_tail))
        raise MediaError("Videoni qayta ishlashda xatolik yuz berdi.")


async def encode_within_limit(
    build_args: Callable[[list[str]], list[str]],
    output: Path,
    info: VideoInfo,
    on_progress: ProgressCallback | None = None,
    timeout: float | None = None,
) -> None:
    """Kodlaydi; natija Telegram limitidan katta chiqsa, bitreytni pasaytirib qayta urinadi."""
    for scale in (1.0, 0.75, 0.5):
        await run_ffmpeg(build_args(encode_args(info, scale)) + [str(output)], info.duration, on_progress, timeout)
        if output.stat().st_size <= settings.upload_limit_bytes:
            return
        logger.info("Natija %d bayt — limitdan katta, qayta kodlanadi", output.stat().st_size)
    raise MediaError("Natijaviy video Telegram limitiga sig'madi. Qisqaroq video yuboring.")


async def comparison_image(src: Path, dst: Path, info: VideoInfo, out: Path) -> bool:
    """Videoning o'rtasidagi bitta kadrdan "asl | yaxshilangan" solishtirma rasm yasaydi."""
    at = f"{info.duration / 2:.2f}"
    vertical = info.height > info.width
    # Vertikal video — yonma-yon, gorizontal — ustma-ust (rasm telefonda kattaroq ko'rinadi)
    size = "-2:1280" if vertical else "1280:-2"
    stack = "hstack" if vertical else "vstack"
    code, _, err = await _run([
        settings.FFMPEG_BIN, "-hide_banner", "-y", "-ss", at, "-i", str(src), "-ss", at, "-i", str(dst),
        "-filter_complex",
        f"[0:v]scale={size}:flags=lanczos,setsar=1[a];[1:v]scale={size}:flags=lanczos,setsar=1[b];"
        f"[a]pad=iw+12:ih:0:0:white[a2];[a2][b]{stack}=inputs=2" if vertical else
        f"[0:v]scale={size}:flags=lanczos,setsar=1[a];[1:v]scale={size}:flags=lanczos,setsar=1[b];"
        f"[a]pad=iw:ih+12:0:0:white[a2];[a2][b]{stack}=inputs=2",
        "-frames:v", "1", "-q:v", "2", str(out),
    ], timeout=120)
    if code != 0:
        logger.warning("Solishtirma rasm yasalmadi: %s", err[-500:])
    return code == 0 and out.exists()
