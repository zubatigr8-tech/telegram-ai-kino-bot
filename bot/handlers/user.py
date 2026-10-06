"""Oddiy foydalanuvchi bo'limlari: Shorts, Premium (karta orqali to'lov) va kanal zayavkalari."""
import logging
from html import escape as h

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from bot.handlers.admin_panel import send_payment_to_admin
from bot.handlers.movie import send_movie
from bot.join_requests import handle_join_request
from bot.keyboards import BTN_PREMIUM, BTN_SHORTS
from bot.services import (
    CARD_NUMBER,
    CARD_OWNER,
    PREMIUM_PRICE,
    all_admin_ids,
    fmt_date,
    get_setting,
    premium_enabled,
    user_is_premium,
)
from bot.states import UserFlow
from shared.db.database import get_session
from shared.db.models import Payment, Short, User

logger = logging.getLogger(__name__)
router = Router(name="user")


# ---------- 🎬 Shorts ----------


async def send_short(bot, chat_id: int, after_id: int = 0) -> bool:
    """after_id'dan keyingi shortni yuboradi; oxiriga yetganda boshidan boshlaydi."""
    async with get_session() as session:
        short = (
            await session.execute(select(Short).where(Short.id > after_id).order_by(Short.id).limit(1))
        ).scalar_one_or_none()
        if short is None and after_id:
            short = (await session.execute(select(Short).order_by(Short.id).limit(1))).scalar_one_or_none()
    if short is None:
        return False
    kb = InlineKeyboardBuilder()
    if short.movie_code:
        kb.button(text="🎬 To'liq kino", callback_data=f"sh:movie:{short.movie_code}")
    kb.button(text="▶️ Keyingisi", callback_data=f"sh:next:{short.id}")
    kb.adjust(2)
    caption = h(short.caption or "")
    if short.movie_code:
        caption = (caption + f"\n\n🔢 Kino kodi: <b>{short.movie_code}</b>").strip()
    await bot.send_video(chat_id, short.file_id, caption=caption[:1024] or None, reply_markup=kb.as_markup())
    return True


@router.message(F.text == BTN_SHORTS)
async def shorts(message: Message) -> None:
    if not await send_short(message.bot, message.chat.id):
        await message.answer("📹 Hozircha shorts yo'q. Tez orada qo'shiladi!")


@router.callback_query(F.data.startswith("sh:next:"))
async def shorts_next(callback: CallbackQuery) -> None:
    await callback.answer()
    await send_short(callback.bot, callback.from_user.id, int(callback.data.split(":")[-1]))


@router.callback_query(F.data.startswith("sh:movie:"))
async def shorts_movie(callback: CallbackQuery) -> None:
    code = int(callback.data.split(":")[-1])
    if await send_movie(callback.bot, callback.from_user.id, code):
        await callback.answer()
    else:
        await callback.answer("Kino topilmadi.", show_alert=True)


# ---------- 💎 Premium ----------


async def premium_info_text(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    if not await premium_enabled():
        return "💎 Premium hozircha mavjud emas.", None
    async with get_session() as session:
        user = await session.get(User, user_id)
    if user_is_premium(user):
        return f"💎 Sizda premium faol: <b>{fmt_date(user.premium_until)}</b> gacha.", None

    number = await get_setting(CARD_NUMBER)
    if not number:
        return "💎 Premium tez orada ishga tushadi. Hozircha to'lov kartasi kiritilmagan.", None
    owner = await get_setting(CARD_OWNER, "—")
    price = await get_setting(PREMIUM_PRICE, "admin bilan kelishiladi")
    text = (
        "💎 <b>Premium</b>\n\n"
        "Premium bilan majburiy kanallarga obuna bo'lmasdan barcha kinolarni olasiz.\n\n"
        f"💰 Narxi: <b>{h(price)}</b>\n"
        f"💳 Karta: <code>{h(number)}</code>\n"
        f"👤 Karta egasi: <b>{h(owner)}</b>\n\n"
        "To'lovni amalga oshirgach, pastdagi tugmani bosib <b>chek rasmini</b> yuboring. "
        "Admin tekshirib, premiumni faollashtiradi."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📸 Chekni yuborish", callback_data="prem:pay")]]
    )
    return text, kb


@router.message(F.text == BTN_PREMIUM)
async def premium_info(message: Message) -> None:
    text, kb = await premium_info_text(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "prem:info")
async def premium_info_cb(callback: CallbackQuery) -> None:
    text, kb = await premium_info_text(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "prem:pay")
async def premium_pay(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(UserFlow.send_receipt)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="prem:cancel")]])
    await callback.message.answer("📸 To'lov chekining rasmini (skrinshotini) yuboring:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "prem:cancel")
async def premium_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.message(UserFlow.send_receipt, F.photo)
async def premium_receipt(message: Message, state: FSMContext) -> None:
    async with get_session() as session:
        payment = Payment(user_id=message.from_user.id, photo_file_id=message.photo[-1].file_id)
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
    await state.clear()
    sent = 0
    for admin_id in all_admin_ids():
        try:
            await send_payment_to_admin(message.bot, admin_id, payment)
            sent += 1
        except Exception:
            logger.warning("Chekni adminga yuborib bo'lmadi: %s", admin_id)
    await message.answer(
        "✅ Chekingiz adminga yuborildi. Tasdiqlangach, sizga xabar keladi."
        if sent
        else "⚠️ Chekni hozir adminga yetkazib bo'lmadi, birozdan so'ng qayta urinib ko'ring."
    )


@router.message(UserFlow.send_receipt)
async def premium_receipt_wrong(message: Message) -> None:
    await message.answer("Iltimos, to'lov chekining <b>rasmini</b> yuboring.")


# ---------- 📨 Kanal zayavkalari ----------


@router.chat_join_request()
async def join_request(request: ChatJoinRequest) -> None:
    """Majburiy kanalga kelgan qo'shilish so'rovi faqat ro'yxatga olinadi (bot uni TASDIQLAMAYDI —
    buni kanal admini o'zi qiladi). Foydalanuvchi obuna bo'lgan hisoblanadi va unga xabar yuboriladi."""
    if not await handle_join_request(request):
        return
    me = await request.bot.me()
    text = (
        f"📨 <b>{h(request.chat.title or 'Kanal')}</b> kanaliga so'rovingiz qabul qilindi.\n\n"
        "🎬 Kinolarni olish uchun botni oching va kino kodini yuboring."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎬 Botni ochish", url=f"https://t.me/{me.username}?start=join")]]
    )
    try:
        # Telegram zayavka yuborgan odamga bot 5 daqiqa ichida yozishiga ruxsat beradi
        await request.bot.send_message(request.user_chat_id, text, reply_markup=kb)
    except Exception as exc:
        logger.info("Zayavka egasiga xabar yuborib bo'lmadi: %s", exc)
