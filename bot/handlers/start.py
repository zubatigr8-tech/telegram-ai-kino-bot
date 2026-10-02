from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.channels import ensure_channel_links, get_active_channels, is_subscribed
from bot.handlers.movie import send_movie
from bot.join_requests import owned_channels
from bot.keyboards import subscription_keyboard, user_menu_kb
from bot.services import premium_enabled

router = Router(name="start")

WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "🎬 Kinoni olish uchun kino kodini (raqamini) yuboring, masalan: <b>7</b>"
)
PENDING_CODE_KEY = "pending_code"


async def menu_kb(user_id: int, is_admin: bool):
    return user_menu_kb(is_admin, await premium_enabled(), is_owner=bool(await owned_channels(user_id)))


def start_code(command: CommandObject | None) -> int | None:
    """Kanal postidagi "Kinoni ko'rish" tugmasi botni /start <kod> bilan ochadi."""
    args = (command.args or "").strip() if command else ""
    return int(args) if args.isdigit() and len(args) <= 9 else None


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject, is_admin: bool = False) -> None:
    # /start'ga faqat kanal(lar)ga obuna bo'lgan (yoki premium) foydalanuvchi yetib keladi —
    # obuna bo'lmaganlarga SubscriptionMiddleware kanallar ro'yxatini ko'rsatadi.
    await state.clear()
    kb = await menu_kb(message.from_user.id, is_admin)
    code = start_code(command)
    if code is not None and await send_movie(message.bot, message.chat.id, code):
        await message.answer("🎬 Boshqa kino uchun kodini yuboring.", reply_markup=kb)
        return
    await message.answer(WELCOME_TEXT, reply_markup=kb)


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext, is_admin: bool = False) -> None:
    # Bu callback SubscriptionMiddleware'dan ozod qilingan, shuning uchun obunani shu yerda tekshiramiz
    channels = await get_active_channels()
    if channels and not await is_subscribed(callback.bot, callback.from_user.id, channels):
        await callback.answer("❌ Hali barcha kanallarga obuna bo'lmagansiz.", show_alert=True)
        if callback.message:
            await ensure_channel_links(callback.bot, channels)
            try:
                await callback.message.edit_reply_markup(
                    reply_markup=subscription_keyboard(channels, await premium_enabled())
                )
            except Exception:
                pass  # tugmalar o'zgarmagan bo'lsa Telegram "message is not modified" qaytaradi
        return

    await callback.answer("Rahmat! Obuna tasdiqlandi ✅")
    data = await state.get_data()
    code = data.get(PENDING_CODE_KEY)
    await state.update_data({PENDING_CODE_KEY: None})
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
    kb = await menu_kb(callback.from_user.id, is_admin)
    if code is not None and await send_movie(callback.bot, callback.from_user.id, code):
        await callback.bot.send_message(
            callback.from_user.id, "✅ Obuna tasdiqlandi!\n\n🎬 Boshqa kino uchun kodini yuboring.", reply_markup=kb
        )
        return
    await callback.bot.send_message(
        callback.from_user.id,
        "✅ Obuna tasdiqlandi!\n\n🎬 Endi kino kodini (raqamini) yuboring, masalan: <b>7</b>",
        reply_markup=kb,
    )
