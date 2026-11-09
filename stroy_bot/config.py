"""Qurilish mollari boti sozlamalari. Hammasi stroy_bot/.env faylidan o'qiladi.

Kino bot bilan bitta serverda ishlaganda ham to'qnashmasligi uchun
o'zgaruvchi nomlari STROY_ bilan boshlanadi.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BOT_DIR = Path(__file__).resolve().parent
load_dotenv(BOT_DIR / ".env")


def _split_ids(raw: str) -> set[int]:
    return {int(part) for part in (p.strip() for p in raw.split(",")) if part.isdigit()}


class Settings:
    BOT_TOKEN: str = os.getenv("STROY_BOT_TOKEN", "")
    # Zayavkalar (mijoz so'rovlari) shu ID larga yuboriladi
    ADMIN_IDS: set[int] = _split_ids(os.getenv("STROY_ADMIN_IDS", ""))

    # ANTHROPIC_API_KEY ni SDK o'zi muhitdan o'qiydi
    AI_MODEL: str = os.getenv("STROY_AI_MODEL", "claude-opus-5-5")
    # low | medium | high — suhbat uchun "low" tez va arzon
    AI_EFFORT: str = os.getenv("STROY_AI_EFFORT", "low")
    # Har bir mijoz uchun xotirada saqlanadigan oxirgi xabarlar soni
    HISTORY_LIMIT: int = int(os.getenv("STROY_HISTORY_LIMIT", "20"))

    STORE_INFO_FILE: Path = Path(os.getenv("STROY_STORE_INFO_FILE", str(BOT_DIR / "store_info.md")))


settings = Settings()
