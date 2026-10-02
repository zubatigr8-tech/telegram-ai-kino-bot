"""Video sifatini oshiruvchi botning barcha sozlamalari — .env faylidan o'qiladi."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Qaysi "dvigatel" bilan ishlov beriladi: ffmpeg | realesrgan | replicate
    ENGINE: str = os.getenv("ENGINE", "ffmpeg").strip().lower()

    # Natijaviy video balandligi (720, 1080, 1440, 2160). Asl video bundan kichik bo'lsa kattalashtiriladi.
    TARGET_HEIGHT: int = int(os.getenv("TARGET_HEIGHT", "1080"))
    # Bitta videoning ruxsat etilgan eng uzun davomiyligi (soniya)
    MAX_DURATION_SEC: int = int(os.getenv("MAX_DURATION_SEC", "180"))
    # Bir vaqtda nechta video ishlanadi (ishlov berish juda og'ir — odatda 1)
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))
    # Navbatda kutishi mumkin bo'lgan eng ko'p videolar soni
    MAX_QUEUE_SIZE: int = int(os.getenv("MAX_QUEUE_SIZE", "20"))
    # Bitta videoga ajratiladigan eng ko'p vaqt (soniya)
    JOB_TIMEOUT_SEC: int = int(os.getenv("JOB_TIMEOUT_SEC", "3600"))
    # Vaqtinchalik fayllar papkasi
    WORK_DIR: Path = Path(os.getenv("WORK_DIR", str(BASE_DIR / "work")))

    # Telegram Bot API serveri. Oddiy (bulutli) API: yuklab olish ≤20 MB, yuborish ≤50 MB.
    # O'zingizning Local Bot API serveringiz bo'lsa ikkalasi ham 2000 MB gacha.
    TELEGRAM_API_URL: str = os.getenv("TELEGRAM_API_URL", "").strip()
    TELEGRAM_API_LOCAL: bool = _bool("TELEGRAM_API_LOCAL")

    # --- ffmpeg ---
    FFMPEG_BIN: str = os.getenv("FFMPEG_BIN", "ffmpeg")
    FFPROBE_BIN: str = os.getenv("FFPROBE_BIN", "ffprobe")
    # libx264 preset: tezroq = ultrafast..medium, sifatliroq = slow/slower
    X264_PRESET: str = os.getenv("X264_PRESET", "medium")
    # ffmpeg oqimlari soni. Konteyner serverning barcha yadrolarini "ko'radi" — cheklanmasa x264 o'nlab
    # oqim ochib, 1 GB xotirali tarifda jarayon o'ldiriladi (OOM). 2 oqim ≈ 400 MB.
    FFMPEG_THREADS: int = int(os.getenv("FFMPEG_THREADS", "2"))

    # --- Real-ESRGAN (lokal, GPU tavsiya etiladi) ---
    REALESRGAN_BIN: str = os.getenv("REALESRGAN_BIN", "realesrgan-ncnn-vulkan")
    REALESRGAN_MODEL: str = os.getenv("REALESRGAN_MODEL", "realesrgan-x4plus")
    REALESRGAN_SCALE: int = int(os.getenv("REALESRGAN_SCALE", "4"))
    REALESRGAN_GPU: str = os.getenv("REALESRGAN_GPU", "")  # masalan "0"; bo'sh = avtomatik

    # --- Replicate (bulutli AI, pullik) ---
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN", "")
    REPLICATE_API_URL: str = os.getenv("REPLICATE_API_URL", "https://api.replicate.com/v1")
    REPLICATE_MODEL: str = os.getenv("REPLICATE_MODEL", "topazlabs/video-upscale")
    # Model video faylni qaysi maydon nomi bilan qabul qiladi
    REPLICATE_VIDEO_FIELD: str = os.getenv("REPLICATE_VIDEO_FIELD", "video")
    # Modelga qo'shimcha parametrlar (JSON)
    REPLICATE_EXTRA_INPUT: dict = json.loads(
        os.getenv("REPLICATE_EXTRA_INPUT", '{"target_resolution": "1080p"}') or "{}"
    )

    @property
    def download_limit_bytes(self) -> int:
        return (2000 if self.TELEGRAM_API_LOCAL else 20) * 1024 * 1024

    @property
    def upload_limit_bytes(self) -> int:
        return (2000 if self.TELEGRAM_API_LOCAL else 50) * 1024 * 1024


settings = Settings()
