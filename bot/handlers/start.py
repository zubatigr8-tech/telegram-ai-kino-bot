from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import subscription_keyboard
from bot.middlewares import get_active_channels, is_subscribed

router = Router(name="start")

WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "🎬 Kino ko'rish uchun kino kodini (raqamini) yuboring, masalan: <b>7</b>\n\n"
    "Boshqa savolingiz bo'lsa, shunchaki yozing — javob beraman.\n"
    "Rasm yoki matnli (.txt) fayl yuborsangiz ham tahlil qilib beraman."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # Foydalanuvchini bazaga yozish va adminlarga xabar berish UserMiddleware'da bajariladi
    await state.clear()
    await message.answer(WELCOME_TEXT)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery) -> None:
    # Bu callback SubscriptionMiddleware'dan ozod qilingan, shuning uchun obunani shu yerda tekshiramiz
    channels = await get_active_channels()
    if channels and not await is_subscribed(callback.bot, callback.from_user.id, channels):
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmagansiz.", show_alert=True)
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=subscription_keyboard(channels))
            except Exception:
                pass  # tugmalar o'zgarmagan bo'lsa Telegram "message is not modified" qaytaradi
        return

    await callback.answer("Rahmat! Obuna tasdiqlandi ✅")
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("Endi kino kodini yuborishingiz mumkin 🎬")
