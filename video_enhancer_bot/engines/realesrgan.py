import asyncio
import logging
import time
from pathlib import Path

from video_enhancer_bot.config import settings
from video_enhancer_bot.media import (
    MediaError, Preset, ProgressCallback, VideoInfo, cleanup_filters, encode_within_limit, finish_filters,
    run_ffmpeg, target_size,
)

logger = logging.getLogger(__name__)


class RealEsrganEngine:
    """Real-ESRGAN neyron tarmog'i bilan har bir kadrni alohida "qayta chizish".

    1) ffmpeg: video → PNG kadrlar (shovqin tozalangan holda)
    2) realesrgan-ncnn-vulkan: har bir kadrni AI bilan kattalashtirish
    3) ffmpeg: kadrlar + asl ovoz → rang/tiniqlik → yakuniy video
    """
    name = "realesrgan"

    async def enhance(
        self, src: Path, dst: Path, info: VideoInfo, preset: Preset, workdir: Path,
        on_progress: ProgressCallback, timeout: float,
    ) -> None:
        deadline = time.monotonic() + timeout
        frames_dir, upscaled_dir = workdir / "frames", workdir / "upscaled"
        frames_dir.mkdir()
        upscaled_dir.mkdir()

        # 1-bosqich (0–10%): kadrlarga ajratish. -r bilan doimiy FPS — kadrlar soni aniq bo'ladi.
        await run_ffmpeg(
            ["-i", str(src), "-map", "0:v:0",
             "-vf", ",".join(cleanup_filters(preset) + [f"scale=in_color_matrix={info.color_matrix}", "format=rgb24"]),
             "-r", info.fps, str(frames_dir / "%08d.png")],
            info.duration, lambda p: on_progress(p * 0.10), deadline - time.monotonic(),
        )
        total = len(list(frames_dir.glob("*.png")))
        if total == 0:
            raise MediaError("Videodan kadrlar ajratib bo'lmadi.")

        # 2-bosqich (10–85%): AI kattalashtirish
        cmd = [settings.REALESRGAN_BIN, "-i", str(frames_dir), "-o", str(upscaled_dir),
               "-n", settings.REALESRGAN_MODEL, "-s", str(settings.REALESRGAN_SCALE), "-f", "png"]
        if settings.REALESRGAN_GPU:
            cmd += ["-g", settings.REALESRGAN_GPU]
        logger.info("Real-ESRGAN: %s", " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"{settings.REALESRGAN_BIN} topilmadi — README'dagi o'rnatish qismini ko'ring") from e

        async def watch_progress() -> None:
            while proc.returncode is None:
                done = sum(1 for _ in upscaled_dir.glob("*.png"))
                await on_progress(0.10 + 0.75 * done / total)
                await asyncio.sleep(3)

        watcher = asyncio.create_task(watch_progress())
        try:
            _, err = await asyncio.wait_for(proc.communicate(), deadline - time.monotonic())
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            await proc.wait()
            raise
        finally:
            watcher.cancel()
        if proc.returncode != 0:
            logger.error("Real-ESRGAN xatosi: %s", err.decode(errors="replace")[-2000:])
            raise MediaError("AI kattalashtirishda xatolik yuz berdi.")

        # Diskni tejash: asl kadrlar endi kerak emas
        for f in frames_dir.glob("*.png"):
            f.unlink()

        # 3-bosqich (85–100%): yig'ish. AI natijasi TARGET_HEIGHT'dan katta bo'lsa ham shu o'lchamga keltiriladi.
        vf = ",".join(finish_filters(preset, target_size(info)))
        await encode_within_limit(
            lambda enc: ["-framerate", info.fps, "-i", str(upscaled_dir / "%08d.png"), "-i", str(src),
                         "-map", "0:v:0", "-map", "1:a:0?", "-vf", vf, "-shortest", *enc],
            dst, info, lambda p: on_progress(0.85 + p * 0.15), deadline - time.monotonic(),
        )
