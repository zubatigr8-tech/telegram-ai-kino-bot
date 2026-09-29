"""Antiradar bot bazasi: foydalanuvchilar, kameralar, to'lovlar."""
import datetime
from contextlib import asynccontextmanager

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from antiradar.config import settings


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def as_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    # SQLite vaqt zonasini saqlamaydi — o'qilgan qiymatni UTC deb hisoblaymiz
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)  # None — hali tanlanmagan
    country: Mapped[str] = mapped_column(String(2), default=settings.COUNTRY)
    # Shaxsiy tezlik chegarasi (km/soat), None — o'chirilgan
    max_speed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trial_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def access_until(self) -> datetime.datetime | None:
        dates = [d for d in (as_utc(self.trial_until), as_utc(self.paid_until)) if d is not None]
        return max(dates) if dates else None

    def has_access(self, now: datetime.datetime | None = None) -> bool:
        until = self.access_until()
        return until is not None and until > (now or utcnow())


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (Index("ix_cameras_lat_lon", "lat", "lon"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), default=settings.COUNTRY)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    # fixed | mobile | red_light | average | police
    kind: Mapped[str] = mapped_column(String(20), default="fixed")
    speed_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)  # km/soat
    # Kamera qaysi yo'nalishdagi harakatni o'lchaydi (0-360°), None — noma'lum / ikki tomonlama
    direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="admin")  # osm | admin | user
    osm_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8))
    # Telegram to'lov ID si — refund uchun kerak, takroriy yozuvdan himoya ham
    charge_id: Mapped[str] = mapped_column(String(255), unique=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_until: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session


async def cameras_near(lat: float, lon: float, radius_m: float) -> list[Camera]:
    """Nuqta atrofidagi kvadrat (bbox) ichidagi faol kameralar. Aniq masofa keyin hisoblanadi."""
    from antiradar.geo import bbox

    min_lat, max_lat, min_lon, max_lon = bbox(lat, lon, radius_m)
    async with get_session() as session:
        rows = await session.scalars(
            select(Camera).where(
                Camera.is_active.is_(True),
                Camera.lat.between(min_lat, max_lat),
                Camera.lon.between(min_lon, max_lon),
            )
        )
        return list(rows)
