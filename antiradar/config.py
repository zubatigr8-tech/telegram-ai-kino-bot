"""Antiradar bot sozlamalari — .env faylidan o'qiladi (kino bot bilan bitta .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _split_ids(raw: str) -> set[int]:
    return {int(p.strip()) for p in raw.split(",") if p.strip().isdigit()}


class Settings:
    BOT_TOKEN: str = os.getenv("ANTIRADAR_BOT_TOKEN", "")
    ADMIN_IDS: set[int] = _split_ids(os.getenv("ANTIRADAR_ADMIN_IDS", os.getenv("ADMIN_IDS", "")))

    DATABASE_URL: str = os.getenv(
        "ANTIRADAR_DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'antiradar.db'}"
    )

    # Hozircha bot faqat O'zbekistonda ishlaydi. Keyin yangi davlat qo'shilganda
    # /start'da davlat tanlash bosqichi qo'shiladi, bazada `country` ustuni allaqachon bor.
    COUNTRY: str = "UZ"

    # Oylik obuna narxi Telegram Stars (⭐) da va bepul sinov davri (kun)
    PRICE_STARS: int = int(os.getenv("ANTIRADAR_PRICE_STARS", "100"))
    TRIAL_DAYS: int = int(os.getenv("ANTIRADAR_TRIAL_DAYS", "3"))

    # Ovozli ogohlantirish (avval ovoz, keyin matn). false — faqat matn
    VOICE_ENABLED: bool = os.getenv("ANTIRADAR_VOICE", "true").lower() not in ("0", "false", "no")
    VOICE_CACHE_DIR: str = os.getenv("ANTIRADAR_VOICE_CACHE_DIR", str(BASE_DIR / "voice_cache"))

    # Bot OpenStreetMap'dan radar va belgilarni necha soatda bir yangilaydi (0 — o'chirilgan)
    OSM_REFRESH_HOURS: float = float(os.getenv("ANTIRADAR_OSM_REFRESH_HOURS", "24"))
    OVERPASS_URL: str = os.getenv("ANTIRADAR_OVERPASS_URL", "https://overpass-api.de/api/interpreter")


settings = Settings()
