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
    # Premium tugash vaqti; None yoki o'tib ketgan bo'lsa — premium yo'q
    premium_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20), default="video")  # video | document
    views: Mapped[int] = mapped_column(Integer, default=0)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    # Botdan yuborilgan xabar (matn, rasm, video...) shu joydan nusxa qilinadi (copy_message)
    copy_from_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    copy_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_channels: Mapped[bool] = mapped_column(Boolean, default=False)  # kanallarga ham post qilinsinmi
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | failed
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Admin(Base):
    """Bot orqali qo'shilgan adminlar. .env'dagi ADMIN_IDS — asosiy (super) adminlar, ular bu jadvalda emas."""

    __tablename__ = "admins"

    tg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Short(Base):
    __tablename__ = "shorts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(255))
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    movie_code: Mapped[int | None] = mapped_column(Integer, nullable=True)  # "To'liq kino" tugmasi uchun
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    """Kalit-qiymat sozlamalar: karta raqami, karta egasi, premium narxi, premium yoqilganmi."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Payment(Base):
    """Premium uchun to'lov cheki. Admin tasdiqlaydi yoki rad etadi."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    photo_file_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JoinRequest(Base):
    """Kanalga qo'shilish so'rovlari (zayavkalar) — statistika uchun."""

    __tablename__ = "join_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
