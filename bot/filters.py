from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from bot.services import is_admin, is_super_admin


class IsAdmin(BaseFilter):
    """.env'dagi ADMIN_IDS va bot orqali qo'shilgan adminlar uchun."""

    async def __call__(self, event: TelegramObject, event_from_user=None) -> bool:
        return event_from_user is not None and is_admin(event_from_user.id)


class IsSuperAdmin(BaseFilter):
    """Faqat .env'dagi ADMIN_IDS uchun (adminlarni boshqarish huquqi)."""

    async def __call__(self, event: TelegramObject, event_from_user=None) -> bool:
        return event_from_user is not None and is_super_admin(event_from_user.id)
