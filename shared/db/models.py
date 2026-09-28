"""SQLAlchemy jadval modellari. Bot va admin panel shu bazani birga ishlatadi."""
import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Yopiq (username'siz) kanallar uchun taklif havolasi — bot uni o'zi yaratadi
    invite_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BroadcastJob(Base):
    __tablename__ = "broadcast_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | failed
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MediaCache(Base):
    """Yuklangan havolalar keshi: bir xil havola qayta yuborilsa, qayta yuklamasdan
    Telegram'dagi file_id orqali darhol yuboriladi."""
    __tablename__ = "media_cache"

    url_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))  # instagram | youtube | tiktok
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    song_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    requests: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SongCache(Base):
    """Topilgan qo'shiqlar: kalit — "ijrochi - nom" (kichik harflarda)."""
    __tablename__ = "song_cache"

    song_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    artist: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shazam_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
