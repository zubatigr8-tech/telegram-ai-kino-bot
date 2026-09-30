from pathlib import Path

from video_enhancer_bot.media import (
    Preset, ProgressCallback, VideoInfo, cleanup_filters, encode_within_limit, finish_filters, target_size,
)


class FfmpegEngine:
    """Hammasi bitta ffmpeg o'tishida: shovqinni tozalash → kattalashtirish → rang → tiniqlik."""
    name = "ffmpeg"

    async def enhance(
        self, src: Path, dst: Path, info: VideoInfo, preset: Preset, workdir: Path,
        on_progress: ProgressCallback, timeout: float,
    ) -> None:
        vf = ",".join(cleanup_filters(preset) + finish_filters(preset, target_size(info)))
        await encode_within_limit(
            lambda enc: ["-i", str(src), "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf, *enc],
            dst, info, on_progress, timeout,
        )
