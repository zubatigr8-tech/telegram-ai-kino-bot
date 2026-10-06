"""Adminlar, sozlamalar va premium bilan ishlash uchun umumiy funksiyalar."""
import datetime

from sqlalchemy import delete, select

from shared.config import settings
from shared.db.database import get_session
from shared.db.models import Admin, Setting, User, utcnow

# ---------- Adminlar ----------
# Har xabarda bazaga murojaat qilmaslik uchun bot orqali qo'shilgan adminlar xotirada saqlanadi.
# Bot bitta jarayonda ishlaydi, shuning uchun qo'shish/o'chirishda kesh darhol yangilanadi.
_db_admins: set[int] = set()


async def load_admins() -> None:
    async with get_session() as session:
        result = await session.execute(select(Admin.tg_id))
        _db_admins.clear()
        _db_admins.update(row[0] for row in result.all())


def is_super_admin(user_id: int) -> bool:
    """.env'dagi ADMIN_IDS — asosiy adminlar. Faqat ular boshqa adminlarni qo'sha/o'chira oladi."""
    return user_id in settings.ADMIN_IDS


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS or user_id in _db_admins


def all_admin_ids() -> set[int]:
    return set(settings.ADMIN_IDS) | _db_admins


async def add_admin(user_id: int, added_by: int) -> bool:
    if is_admin(user_id):
        return False
    async with get_session() as session:
        session.add(Admin(tg_id=user_id, added_by=added_by))
        await session.commit()
    _db_admins.add(user_id)
    return True


async def remove_admin(user_id: int) -> bool:
    if user_id not in _db_admins:
        return False
    async with get_session() as session:
        await session.execute(delete(Admin).where(Admin.tg_id == user_id))
        await session.commit()
    _db_admins.discard(user_id)
    return True


# ---------- Sozlamalar ----------
CARD_NUMBER = "card_number"
CARD_OWNER = "card_owner"
PREMIUM_PRICE = "premium_price"
PREMIUM_ENABLED = "premium_enabled"


async def get_setting(key: str, default: str | None = None) -> str | None:
    async with get_session() as session:
        row = await session.get(Setting, key)
        return row.value if row else default


async def set_setting(key: str, value: str) -> None:
    async with get_session() as session:
        row = await session.get(Setting, key)
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
        await session.commit()


async def premium_enabled() -> bool:
    return (await get_setting(PREMIUM_ENABLED, "1")) == "1"


# ---------- Premium ----------
def as_utc(dt: datetime.datetime | None) -> datetime.datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)  # SQLite vaqt mintaqasini saqlamaydi
    return dt


def user_is_premium(user: User | None) -> bool:
    if user is None or user.premium_until is None:
        return False
    return as_utc(user.premium_until) > utcnow()


async def is_premium(user_id: int) -> bool:
    async with get_session() as session:
        return user_is_premium(await session.get(User, user_id))


async def grant_premium(user_id: int, days: int) -> datetime.datetime | None:
    """Premiumni `days` kunga uzaytiradi (amaldagi muddat ustiga qo'shiladi). Yangi tugash vaqtini qaytaradi."""
    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None:
            return None
        start = as_utc(user.premium_until) if user_is_premium(user) else utcnow()
        user.premium_until = start + datetime.timedelta(days=days)
        await session.commit()
        return user.premium_until


async def revoke_premium(user_id: int) -> bool:
    async with get_session() as session:
        user = await session.get(User, user_id)
        if user is None or not user_is_premium(user):
            return False
        user.premium_until = None
        await session.commit()
        return True


def fmt_date(dt: datetime.datetime | None) -> str:
    if dt is None:
        return "—"
    # O'zbekiston vaqti (UTC+5)
    return as_utc(dt).astimezone(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%Y %H:%M")
