"""Async DB ulanishi. Bot va admin panel shu modullardan foydalanadi."""
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.config import settings
from shared.db.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Mavjud bazaga keyinroq qo'shilgan ustunlar: (jadval, ustun, SQL turi).
# create_all faqat yangi jadval yaratadi, eski jadvalga ustun qo'shmaydi — shuning uchun shu yerda qo'shamiz.
_ADDED_COLUMNS = [
    ("channels", "invite_link", "VARCHAR(255)"),
]


def _add_missing_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    for table, column, sql_type in _ADDED_COLUMNS:
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))


_init_lock = asyncio.Lock()
_initialized = False


async def init_db() -> None:
    # run_all.py'da bot va admin panel init_db'ni bir vaqtda chaqiradi — yangi bazada
    # ikkalasi jadval yaratishga urinib "table already exists" xatosini bermasligi uchun qulf kerak
    global _initialized
    async with _init_lock:
        if _initialized:
            return
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_add_missing_columns)
        _initialized = True


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session
