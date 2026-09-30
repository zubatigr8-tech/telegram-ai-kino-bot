"""Sifatni oshirish "dvigatellari". Hammasi bir xil interfeysga ega:

    await engine.enhance(src, dst, info, preset, workdir, on_progress, timeout)

- ffmpeg      — bepul, istalgan serverda (GPU kerak emas) ishlaydi, klassik filtrlar
- realesrgan  — lokal neyron tarmoq (Real-ESRGAN), eng yaxshi natija, GPU tavsiya etiladi
- replicate   — bulutdagi AI model (masalan Topaz Video Upscale), pullik, server kuchi kerak emas
"""
from pathlib import Path
from typing import Protocol

from video_enhancer_bot.config import settings
from video_enhancer_bot.media import Preset, ProgressCallback, VideoInfo


class Engine(Protocol):
    name: str

    async def enhance(
        self, src: Path, dst: Path, info: VideoInfo, preset: Preset, workdir: Path,
        on_progress: ProgressCallback, timeout: float,
    ) -> None: ...


def get_engine() -> Engine:
    if settings.ENGINE == "realesrgan":
        from video_enhancer_bot.engines.realesrgan import RealEsrganEngine
        return RealEsrganEngine()
    if settings.ENGINE == "replicate":
        from video_enhancer_bot.engines.replicate import ReplicateEngine
        return ReplicateEngine()
    if settings.ENGINE != "ffmpeg":
        raise RuntimeError(f"Noma'lum ENGINE={settings.ENGINE!r}. ffmpeg, realesrgan yoki replicate bo'lishi kerak.")
    from video_enhancer_bot.engines.ffmpeg import FfmpegEngine
    return FfmpegEngine()
