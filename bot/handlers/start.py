from html import escape as h

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from shared.config import settings
from shared.db.database import get_session
from shared.db.models import User, utcnow

router = Router(name="start")

WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "🎬 Kino ko'rish uchun kino kodini (raqamini) yuboring, masalan: <b>7</b>\n\n"
    "Boshqa savolingiz bo'lsa, shunchaki yozing — javob beraman.\n"
    "Rasm yoki matnli (.txt) fayl yuborsangiz ham tahlil qilib beraman."
)


async def upsert_user(message: Message) -> bool:
    """Foydalanuvchini bazaga yozadi. True qaytarsa — bu YANGI foydalanuvchi."""
    async with get_session() as session:
        user = await session.get(User, message.from_user.id)
        is_new = user is None
        if user is None:
            user = User(
                tg_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            session.add(user)
        else:
            user.username = message.from_user.username
            user.full_name = message.from_user.full_name
            user.last_active = utcnow()
        await session.commit()
    return is_new


async def notify_admins_new_user(message: Message) -> None:
    label = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.full_name or "—")
    text = (
        "🆕 <b>Yangi obunachi!</b>\n\n"
        f"👤 {h(label)}\n"
        f"ID: <code>{message.from_user.id}</code>"
    )
    for admin_id in settings.ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, text)
        except Exception:
            pass  # admin botni hali /start qilmagan bo'lishi mumkin — o'tkazib yuboramiz


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_new = await upsert_user(message)
    if is_new:
        await notify_admins_new_user(message)
    await message.answer(WELCOME_TEXT)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext) -> None:
    # Bu callback SubscriptionMiddleware tomonidan qayta tekshiriladi;
    # agar shu yerga yetib kelgan bo'lsa, demak foydalanuvchi endi obuna bo'lgan.
    await callback.answer("Rahmat! Obuna tasdiqlandi ✅")
    if callback.message:
        await callback.message.answer("Endi kino kodini yuborishingiz mumkin 🎬")
