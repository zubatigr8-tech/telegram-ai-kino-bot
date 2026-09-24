"""Loyihaning barcha sozlamalari shu yerda, .env faylidan o'qiladi."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _split_ids(raw: str) -> set[int]:
    result = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: set[int] = _split_ids(os.getenv("ADMIN_IDS", ""))

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'bot_database.db'}"
    )
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups"))

    ADMIN_PANEL_SECRET_KEY: str = os.getenv("ADMIN_PANEL_SECRET_KEY", "dev-secret-key")
    ADMIN_PANEL_USERNAME: str = os.getenv("ADMIN_PANEL_USERNAME", "admin")
    ADMIN_PANEL_PASSWORD: str = os.getenv("ADMIN_PANEL_PASSWORD", "admin")
    ADMIN_PANEL_HOST: str = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    ADMIN_PANEL_PORT: int = int(os.getenv("ADMIN_PANEL_PORT", "8000"))


settings = Settings()
