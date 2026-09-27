from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot.keyboards import subscription_keyboard
from bot.middlewares import get_active_channels, is_subscribed

router = Router(name="start")

WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "🎬 Kinoni olish uchun kino kodini (raqamini) yuboring, masalan: <b>7</b>"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # /start'ga faqat kanal(lar)ga obuna bo'lgan foydalanuvchi yetib keladi —
    # obuna bo'lmaganlarga SubscriptionMiddleware kanallar ro'yxatini ko'rsatadi.
    # ReplyKeyboardRemove — eski versiyadan qolgan pastki tugmalarni o'chiradi.
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=ReplyKeyboardRemove())


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
        await callback.message.answer(
            "✅ Obuna tasdiqlandi!\n\n🎬 Endi kino kodini (raqamini) yuboring, masalan: <b>7</b>",
            reply_markup=ReplyKeyboardRemove(),
        )
