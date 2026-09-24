"""Ma'lumotlar bazasini vaqti-vaqti bilan avtomatik zaxiralab boradi (backups/ papkasiga)."""
import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from shared.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path(settings.BACKUP_DIR)
BACKUP_INTERVAL_SECONDS = 6 * 60 * 60  # har 6 soatda
MAX_BACKUPS = 20  # oxirgi 20 ta zaxira saqlanadi, eskilari avtomatik o'chiriladi


def _get_sqlite_path() -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not settings.DATABASE_URL.startswith(prefix):
        return None  # SQLite emas (masalan PostgreSQL) — bu holda zaxiralash o'chirilgan
    return Path(settings.DATABASE_URL[len(prefix):])


async def _make_backup() -> None:
    db_path = _get_sqlite_path()
    if db_path is None or not db_path.exists():
        return

    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"bot_database_{stamp}.db"
    shutil.copy2(db_path, dest)
    logger.info("Zaxira nusxa yaratildi: %s", dest.name)

    backups = sorted(BACKUP_DIR.glob("bot_database_*.db"))
    while len(backups) > MAX_BACKUPS:
        backups.pop(0).unlink(missing_ok=True)


async def run_backup_worker() -> None:
    await _make_backup()  # bot ishga tushganda ham darhol bitta zaxira olamiz
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_SECONDS)
        try:
            await _make_backup()
        except Exception:
            logger.exception("Zaxira nusxalashda xatolik")
