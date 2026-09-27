"""Async DB ulanishi. Bot va admin panel shu modullardan foydalanadi."""
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.config import settings
from shared.db.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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
        _initialized = True


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session
