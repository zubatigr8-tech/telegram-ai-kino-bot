"""Telegram ichidagi admin panel — .env'dagi ADMIN_IDS va bot orqali qo'shilgan adminlar uchun.
Pastki tugmalar (reply keyboard) orqali boshqariladi: kinolar, shorts, kanallar, xabar yuborish,
premium, karta sozlamalari, adminlar."""
import datetime
import platform
import re
import time
from html import escape as h

from aiogram import F, Router
from aiogram.enums import MessageOriginType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from bot import keyboards as kbs
from bot.channels import ChannelError, channel_url, clean_username, fetch_channel_info
from bot.filters import IsAdmin
from bot.handlers.movie import movie_caption
from bot.join_requests import channel_stats_text, create_request_link, request_counts
from bot.services import (
    AUTO_APPROVE,
    CARD_NUMBER,
    CARD_OWNER,
    PREMIUM_ENABLED,
    PREMIUM_PRICE,
    add_admin,
    all_admin_ids,
    fmt_date,
    get_setting,
    grant_premium,
    is_admin,
    is_super_admin,
    premium_enabled,
    remove_admin,
    revoke_premium,
    set_setting,
    user_is_premium,
)
from bot.states import AdminFlow
from shared.config import settings
from shared.db.database import get_session
from shared.db.models import BroadcastJob, Channel, JoinRequest, Movie, Payment, Short, User, utcnow

# menu — pastki menyu tugmalari. U `router`dan OLDIN ulanadi (bot/main.py), shuning uchun admin biror
# jarayon o'rtasida (masalan, "kod yuboring" bosqichida) tugma bossa ham, tugma ishlaydi va jarayon bekor bo'ladi.
menu = Router(name="admin_menu")
menu.message.filter(IsAdmin())
# router — bosqichma-bosqich jarayonlar va inline tugmalar
router = Router(name="admin_panel")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

STARTED_AT = time.monotonic()
MAX_CODE = 999_999_999


def cancel_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    return kb.as_markup()


async def next_free_code() -> int:
    async with get_session() as session:
        max_code = (await session.execute(select(func.max(Movie.code)))).scalar_one()
    return (max_code or 0) + 1


async def get_movie(code: int) -> Movie | None:
    async with get_session() as session:
        return (await session.execute(select(Movie).where(Movie.code == code))).scalar_one_or_none()


def user_label(u: User) -> str:
    return f"@{u.username}" if u.username else (u.full_name or str(u.tg_id))


# ======================================================================
# Menyu tugmalari (`menu` router) HAR QANDAY holatda ishlaydi va boshlangan jarayonni almashtiradi.
# ======================================================================


@menu.message(Command("admin"))
@menu.message(F.text == kbs.BTN_ADMIN_PANEL)
async def admin_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Admin paneliga xush kelibsiz!", reply_markup=kbs.admin_menu_kb())


@menu.message(F.text == kbs.BTN_HOME)
async def go_home(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "🏠 Bosh sahifa. Kino kodini yuboring yoki pastdagi tugmalardan foydalaning.",
        reply_markup=kbs.user_menu_kb(True, await premium_enabled()),
    )


@router.callback_query(F.data == "adm:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.edit_text("❌ Bekor qilindi.")
    except Exception:
        await callback.message.answer("❌ Bekor qilindi.")
    await callback.answer()


# ---------- 📈 Statistika ----------


@menu.message(F.text == kbs.BTN_STATS)
async def stats(message: Message, state: FSMContext) -> None:
    await state.clear()
    now = utcnow()
    day_ago = now - datetime.timedelta(days=1)
    async with get_session() as session:
        async def count(stmt):
            return (await session.execute(stmt)).scalar_one() or 0

        total_users = await count(select(func.count(User.tg_id)))
        blocked = await count(select(func.count(User.tg_id)).where(User.is_blocked == True))  # noqa: E712
        new_today = await count(select(func.count(User.tg_id)).where(User.joined_at >= day_ago))
        active_today = await count(select(func.count(User.tg_id)).where(User.last_active >= day_ago))
        premium = await count(select(func.count(User.tg_id)).where(User.premium_until > now))
        total_movies = await count(select(func.count(Movie.id)))
        total_views = await count(select(func.sum(Movie.views)))
        total_shorts = await count(select(func.count(Short.id)))
        total_channels = await count(select(func.count(Channel.id)))
        join_requests = await count(select(func.count(JoinRequest.id)))
        total_sent = await count(select(func.sum(BroadcastJob.sent_count)))
        top = (await session.execute(select(Movie).order_by(Movie.views.desc()).limit(5))).scalars().all()

    top_text = "\n".join(f"  {i}. <b>{m.code}</b> — {h(m.title)} ({m.views} marta)" for i, m in enumerate(top, 1))
    await message.answer(
        "📈 <b>Statistika</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🆕 So'nggi 24 soatda qo'shilgan: <b>{new_today}</b>\n"
        f"🔥 So'nggi 24 soatda faol: <b>{active_today}</b>\n"
        f"🚫 Bloklangan: <b>{blocked}</b>\n"
        f"💎 Premium: <b>{premium}</b>\n\n"
        f"🎬 Kinolar: <b>{total_movies}</b> (jami ko'rishlar: <b>{total_views}</b>)\n"
        f"📹 Shorts: <b>{total_shorts}</b>\n"
        f"📣 Majburiy kanallar: <b>{total_channels}</b>\n"
        f"📨 Kanal zayavkalari: <b>{join_requests}</b>\n"
        f"✉️ Jami yuborilgan xabarlar: <b>{total_sent}</b>"
        + (f"\n\n🏆 <b>Eng ko'p ko'rilgan kinolar:</b>\n{top_text}" if top else "")
    )


# ---------- 🤖 Bot holati ----------


@menu.message(F.text == kbs.BTN_BOT_STATUS)
async def bot_status(message: Message, state: FSMContext) -> None:
    await state.clear()
    uptime = int(time.monotonic() - STARTED_AT)
    days, rem = divmod(uptime, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60

    async with get_session() as session:
        pending = (
            await session.execute(
                select(func.count(BroadcastJob.id)).where(BroadcastJob.status.in_(("pending", "sending")))
            )
        ).scalar_one()
        pending_payments = (
            await session.execute(select(func.count(Payment.id)).where(Payment.status == "pending"))
        ).scalar_one()
        channels = list((await session.execute(select(Channel))).scalars().all())

    me = await message.bot.me()
    lines = []
    for ch in channels:
        try:
            member = await message.bot.get_chat_member(ch.chat_id, me.id)
            ok = member.status in ("administrator", "creator")
        except Exception:
            ok = False
        mark = "✅ admin" if ok else "❌ admin emas"
        lines.append(f"  • {h(ch.title or str(ch.chat_id))} — {mark}")

    await message.answer(
        "🤖 <b>Bot holati</b>\n\n"
        f"✅ Bot ishlayapti: @{me.username}\n"
        f"⏱ Uzluksiz ishlash vaqti: {days} kun {hours} soat {minutes} daqiqa\n"
        f"🐍 Python {platform.python_version()}\n"
        f"✉️ Navbatdagi xabarlar: {pending}\n"
        f"💳 Tasdiqlanmagan to'lovlar: {pending_payments}\n"
        f"💎 Premium tizimi: {'yoqilgan' if await premium_enabled() else 'o‘chirilgan'}\n\n"
        "📣 <b>Kanallarda bot huquqi:</b>\n" + ("\n".join(lines) if lines else "  Kanal qo'shilmagan")
    )


# ---------- 📣 Kanallarni sozlash ----------


async def channels_view(bot) -> tuple[str, InlineKeyboardMarkup]:
    async with get_session() as session:
        channels = list((await session.execute(select(Channel))).scalars().all())
    auto = (await get_setting(AUTO_APPROVE, "1")) == "1"

    if channels:
        lines = []
        for c in channels:
            status = "✅" if c.is_active else "🚫"
            try:
                members = await bot.get_chat_member_count(c.chat_id)
            except Exception:
                members = "—"
            pending, _, total = await request_counts(c.chat_id)
            mode = "📥 yig'ish" if c.collect_requests else "⚡ avto"
            lines.append(
                f"{status} <b>{h(c.title or str(c.chat_id))}</b>\n"
                f"    👥 {members} obunachi | 📨 {total} zayavka (⏳ {pending}) | {mode}"
            )
        body = "\n".join(lines)
    else:
        body = "Hozircha kanal qo'shilmagan (obuna tekshiruvi o'chirilgan)."

    kb = InlineKeyboardBuilder()
    for c in channels:
        kb.row(InlineKeyboardButton(text=f"⚙️ {(c.title or str(c.chat_id))[:30]}", callback_data=f"adm:c:open:{c.id}"))
    kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm:c:add"))
    kb.row(
        InlineKeyboardButton(
            text=f"⚡ Avto-tasdiqlash: {'✅ yoqilgan' if auto else '❌ o‘chirilgan'}",
            callback_data="adm:c:auto",
        )
    )
    text = (
        f"📣 <b>Majburiy kanallar</b>\n\n{body}\n\n"
        "Kanalni sozlash (kanal admini, zayavka yig'ish, hammasini tasdiqlash) uchun uni tanlang.\n"
        "<i>⚡ avto — zayavkalar darhol tasdiqlanadi; 📥 yig'ish — kanal admini keyin hammasini birdan tasdiqlaydi.</i>"
    )
    return text, kb.as_markup()


@menu.message(F.text == kbs.BTN_CHANNELS)
async def channels_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, kb = await channels_view(message.bot)
    await message.answer(text, reply_markup=kb, disable_web_page_preview=True)


async def rerender_channels(callback: CallbackQuery) -> None:
    text, kb = await channels_view(callback.bot)
    try:
        await callback.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        pass  # matn o'zgarmagan bo'lsa Telegram "message is not modified" qaytaradi


async def channel_detail_view(bot, channel_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    async with get_session() as session:
        c = await session.get(Channel, channel_id)
        owner = await session.get(User, c.owner_id) if c and c.owner_id else None
    if c is None:
        return None
    pending, _, _ = await request_counts(c.chat_id)
    owner_text = (
        f"{h(user_label(owner))} (<code>{c.owner_id}</code>)" if owner
        else (f"<code>{c.owner_id}</code>" if c.owner_id else "biriktirilmagan")
    )
    text = (
        f"{await channel_stats_text(bot, c)}\n"
        f"👤 Kanal admini: {owner_text}\n"
        f"🔗 Havola: {h(channel_url(c) or 'yo‘q')}\n"
        f"Holat: {'✅ majburiy obunada' if c.is_active else '🚫 o‘chirilgan'}"
    )
    kb = InlineKeyboardBuilder()
    if pending:
        kb.row(InlineKeyboardButton(text=f"✅ Hammasini tasdiqlash ({pending})", callback_data=f"jr:all:{c.id}"))
    kb.row(
        InlineKeyboardButton(
            text="⚡ Avto-tasdiqlashga o'tish" if c.collect_requests else "📥 Zayavka yig'ishni yoqish",
            callback_data=f"adm:c:mode:{c.id}",
        )
    )
    kb.row(InlineKeyboardButton(text="👤 Kanal adminini belgilash", callback_data=f"adm:c:owner:{c.id}"))
    kb.row(
        InlineKeyboardButton(text="🚫 O'chirish" if c.is_active else "✅ Yoqish", callback_data=f"adm:c:t:{c.id}"),
        InlineKeyboardButton(text="🗑 Ro'yxatdan olib tashlash", callback_data=f"adm:c:d:{c.id}"),
    )
    kb.row(InlineKeyboardButton(text="⬅️ Kanallar ro'yxati", callback_data="adm:c:list"))
    return text, kb.as_markup()


async def rerender_channel_detail(callback: CallbackQuery, channel_id: int) -> None:
    view = await channel_detail_view(callback.bot, channel_id)
    if view is None:
        await rerender_channels(callback)
        return
    try:
        await callback.message.edit_text(view[0], reply_markup=view[1], disable_web_page_preview=True)
    except Exception:
        pass


@router.callback_query(F.data == "adm:c:list")
async def cb_channels_list(callback: CallbackQuery) -> None:
    await callback.answer()
    await rerender_channels(callback)


@router.callback_query(F.data.startswith("adm:c:open:"))
async def cb_channel_open(callback: CallbackQuery) -> None:
    await callback.answer()
    await rerender_channel_detail(callback, int(callback.data.split(":")[-1]))


@router.callback_query(F.data.startswith("adm:c:t:"))
async def cb_toggle_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = not channel.is_active
            await session.commit()
    await callback.answer("Holat o'zgartirildi ✅")
    await rerender_channel_detail(callback, channel_id)


@router.callback_query(F.data.startswith("adm:c:d:"))
async def cb_delete_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            await session.delete(channel)
            await session.commit()
    await callback.answer("O'chirildi ✅")
    await rerender_channels(callback)


@router.callback_query(F.data.startswith("adm:c:mode:"))
async def cb_channel_mode(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel is None:
            await callback.answer("Kanal topilmadi.", show_alert=True)
            return
        if not channel.collect_requests:
            # Yig'ish rejimi uchun zayavka talab qiladigan maxsus havola kerak
            try:
                channel.request_link = await create_request_link(callback.bot, channel)
            except Exception:
                await callback.answer(
                    "Havola yaratib bo'lmadi. Bot kanalda admin va \"Foydalanuvchilarni taklif qilish\" "
                    "huquqi borligini tekshiring.",
                    show_alert=True,
                )
                return
        channel.collect_requests = not channel.collect_requests
        enabled = channel.collect_requests
        await session.commit()
    await callback.answer("📥 Zayavka yig'ish yoqildi" if enabled else "⚡ Avto-tasdiqlash yoqildi")
    await rerender_channel_detail(callback, channel_id)


@router.callback_query(F.data.startswith("adm:c:owner:"))
async def cb_channel_owner(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.channel_owner_id)
    await state.update_data(owner_channel_id=int(callback.data.split(":")[-1]))
    await callback.message.answer(
        "👤 Kanal adminining Telegram ID raqamini yuboring (yoki uning xabarini forward qiling).\n"
        'Kanal adminini olib tashlash uchun "-" yuboring.\n\n'
        "💡 Kanal admini avval botga /start bosishi kerak. O'z ID sini /myid orqali bilishi mumkin.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminFlow.channel_owner_id)
async def channel_owner_receive(message: Message, state: FSMContext) -> None:
    owner_id: int | None = None
    origin = message.forward_origin
    if origin is not None and origin.type == MessageOriginType.USER:
        owner_id = origin.sender_user.id
    elif message.text and message.text.strip() == "-":
        owner_id = None
    elif message.text and re.fullmatch(r"\d{3,15}", message.text.strip()):
        owner_id = int(message.text.strip())
    else:
        await message.answer('Iltimos, ID raqam yuboring, xabar forward qiling yoki "-" yozing.', reply_markup=cancel_kb())
        return

    data = await state.get_data()
    async with get_session() as session:
        channel = await session.get(Channel, data.get("owner_channel_id"))
        if channel is None:
            await state.clear()
            await message.answer("⚠️ Kanal topilmadi.")
            return
        channel.owner_id = owner_id
        title = channel.title or str(channel.chat_id)
        await session.commit()
    await state.clear()
    if owner_id is None:
        await message.answer(f"✅ <b>{h(title)}</b> kanalidan kanal admini olib tashlandi.")
        return
    try:
        await message.bot.send_message(
            owner_id,
            f"👤 Siz <b>{h(title)}</b> kanali uchun kanal admini qilib belgilandingiz!\n\n"
            "Obunachilar va zayavkalar sonini ko'rish hamda zayavkalarni tasdiqlash uchun "
            f"/kanal buyrug'ini yuboring yoki pastdagi «{kbs.BTN_MY_CHANNEL}» tugmasini bosing.",
            reply_markup=kbs.user_menu_kb(is_admin(owner_id), await premium_enabled(), is_owner=True),
        )
        note = "Unga xabar yuborildi."
    except Exception:
        note = "⚠️ Unga xabar yuborib bo'lmadi — u avval botga /start bosishi kerak."
    await message.answer(f"✅ <b>{h(title)}</b> kanaliga kanal admini belgilandi: <code>{owner_id}</code>\n{note}")


@router.callback_query(F.data == "adm:c:auto")
async def cb_toggle_auto_approve(callback: CallbackQuery) -> None:
    auto = (await get_setting(AUTO_APPROVE, "1")) == "1"
    await set_setting(AUTO_APPROVE, "0" if auto else "1")
    await callback.answer("Saqlandi ✅")
    await rerender_channels(callback)


@router.callback_query(F.data == "adm:c:add")
async def cb_add_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_channel_chatid)
    await callback.message.answer(
        "📣 <b>Yangi kanal qo'shish</b>\n\n"
        "1️⃣ Avval botni kanalga <b>admin</b> qilib qo'shing.\n"
        "2️⃣ Keyin shu yerga quyidagilardan birini yuboring:\n"
        "• kanaldan istalgan postni <b>forward</b> qiling (eng oson yo'l);\n"
        "• kanal ID raqami, masalan <code>-1001234567890</code>;\n"
        "• ochiq kanal bo'lsa — <code>@username</code>.\n\n"
        "Kanal nomi va havolasi (yopiq kanal uchun taklif havolasi) bot tomonidan avtomatik olinadi.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


def _channel_ref_from_message(message: Message) -> int | str | None:
    origin = message.forward_origin
    if origin is not None and origin.type == MessageOriginType.CHANNEL:
        return origin.chat.id
    text = (message.text or "").strip()
    if re.fullmatch(r"-?\d{5,18}", text):
        return int(text)
    username = clean_username(text)
    if username:
        return f"@{username}"
    return None


@router.message(AdminFlow.add_channel_chatid)
async def add_channel_receive(message: Message, state: FSMContext) -> None:
    chat_ref = _channel_ref_from_message(message)
    if chat_ref is None:
        await message.answer(
            "Iltimos, kanaldan post forward qiling yoki kanal ID / @username yuboring.",
            reply_markup=cancel_kb(),
        )
        return

    try:
        info = await fetch_channel_info(message.bot, chat_ref)
    except ChannelError as exc:
        await message.answer(f"⚠️ {exc}", reply_markup=cancel_kb())
        return

    async with get_session() as session:
        existing = await session.execute(select(Channel).where(Channel.chat_id == info["chat_id"]))
        if existing.scalar_one_or_none() is not None:
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan.", reply_markup=cancel_kb())
            return
        session.add(Channel(**info))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await message.answer("⚠️ Bu kanal allaqachon qo'shilgan.", reply_markup=cancel_kb())
            return

    await state.clear()
    link = f"https://t.me/{info['username']}" if info["username"] else info["invite_link"]
    await message.answer(
        f"✅ Kanal qo'shildi!\n\n📣 <b>{h(info['title'] or str(info['chat_id']))}</b>\n"
        f"ID: <code>{info['chat_id']}</code>\nHavola: {h(link)}",
        disable_web_page_preview=True,
    )


# ---------- ✉️ Xabar yuborish ----------


@menu.message(F.text == kbs.BTN_BROADCAST)
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.broadcast_message)
    await message.answer(
        "✉️ <b>Xabar yuborish</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring — matn, rasm, video, fayl yoki "
        "kanaldan forward qilingan post bo'lishi mumkin. Xabar aynan shu ko'rinishda yuboriladi.",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.broadcast_message)
async def broadcast_receive(message: Message, state: FSMContext) -> None:
    await state.update_data(
        b_chat_id=message.chat.id,
        b_message_id=message.message_id,
        b_text=(message.html_text if (message.text or message.caption) else "[media]")[:4000],
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Bot foydalanuvchilariga", callback_data="adm:b:send:users")
    kb.button(text="👥 + 📣 Kanallarga ham", callback_data="adm:b:send:all")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(1)
    await message.answer(
        "Xabar yuqoridagi ko'rinishda yuboriladi. Kimlarga yuborilsin?\n\n"
        "📣 <i>Kanallarga ham</i> — xabar bot admin bo'lgan barcha majburiy kanallarga ham post qilinadi, "
        "ya'ni kanal obunachilari ham ko'radi.",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("adm:b:send:"))
async def broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("b_message_id"):
        await callback.answer("Xabar topilmadi, qaytadan boshlang.", show_alert=True)
        return
    to_channels = callback.data.endswith(":all")
    async with get_session() as session:
        session.add(
            BroadcastJob(
                text=data["b_text"],
                copy_from_chat_id=data["b_chat_id"],
                copy_message_id=data["b_message_id"],
                to_channels=to_channels,
            )
        )
        await session.commit()
    await state.clear()
    await callback.message.edit_text(
        "✅ Xabar navbatga qo'yildi, tez orada "
        + ("foydalanuvchilarga va kanallarga" if to_channels else "barcha foydalanuvchilarga")
        + " yuboriladi. Natijani 📈 Statistika bo'limida ko'rishingiz mumkin."
    )
    await callback.answer()


# ---------- 📥 Kino yuklash ----------


@menu.message(F.text == kbs.BTN_MOVIE_ADD)
async def movie_add_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_movie_file)
    await message.answer("📥 <b>Kino yuklash</b>\n\nKino videosi yoki faylini yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_file, F.video | F.document)
async def movie_add_file(message: Message, state: FSMContext) -> None:
    if message.video:
        file_id, file_type = message.video.file_id, "video"
    else:
        file_id, file_type = message.document.file_id, "document"
    await state.update_data(file_id=file_id, file_type=file_type, caption=message.caption)
    await state.set_state(AdminFlow.add_movie_code)
    suggested = await next_free_code()
    await message.answer(
        f"🔢 Iltimos, kino uchun kod kiriting.\n\nBo'sh kod: <code>{suggested}</code> "
        "(nusxa olib yuborishingiz mumkin)",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.add_movie_file)
async def movie_add_wrong_file(message: Message) -> None:
    await message.answer("Iltimos, video yoki fayl yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def movie_add_code(message: Message, state: FSMContext) -> None:
    code = int(message.text)
    if await get_movie(code) is not None:
        await message.answer(f"⚠️ Kod {code} band. Boshqa raqam yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(code=code)
    await state.set_state(AdminFlow.add_movie_title)
    await message.answer("🎬 Kino nomini yuboring:", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_code)
async def movie_add_wrong_code(message: Message) -> None:
    await message.answer("Iltimos, faqat raqam yuboring (ko'pi bilan 9 xonali).", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_title, F.text)
async def movie_add_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip()[:255])
    await state.set_state(AdminFlow.add_movie_description)
    data = await state.get_data()
    hint = "\n\n(Video izohini tavsif qilish uchun <code>+</code> yuboring)" if data.get("caption") else ""
    await message.answer(
        'Tavsif yuboring (yoki "-" deb yozib o\'tkazib yuboring):' + hint, reply_markup=cancel_kb()
    )


@router.message(AdminFlow.add_movie_description, F.text)
async def movie_add_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = message.text.strip()
    description = None if text == "-" else (data.get("caption") if text == "+" else text)

    async with get_session() as session:
        session.add(
            Movie(
                code=data["code"],
                title=data["title"],
                description=description,
                file_id=data["file_id"],
                file_type=data["file_type"],
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await state.set_state(AdminFlow.add_movie_code)
            await message.answer(
                f"⚠️ Kod {data['code']} band bo'lib qoldi. Boshqa kod yuboring:", reply_markup=cancel_kb()
            )
            return

    await state.clear()
    await message.answer(
        f"✅ Kino qo'shildi!\n\n🎬 <b>{h(data['title'])}</b> — kod: <b>{data['code']}</b>\n\n"
        "Kanalga e'lon qilish uchun: 📣 Kino postini yuborish"
    )


# ---------- 🗑 Kino o'chirish ----------


@menu.message(F.text == kbs.BTN_MOVIE_DEL)
async def movie_del_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.delete_movie_code)
    await message.answer("🗑 <b>Kino o'chirish</b>\n\nO'chiriladigan kino kodini yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.delete_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def movie_del_code(message: Message, state: FSMContext) -> None:
    movie = await get_movie(int(message.text))
    if movie is None:
        await message.answer(f"❌ {message.text} raqamli kino topilmadi. Boshqa kod yuboring:", reply_markup=cancel_kb())
        return
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, o'chirilsin", callback_data=f"adm:m:del:{movie.id}")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(1)
    await message.answer(
        f"🎬 <b>{h(movie.title)}</b> (kod: {movie.code})\n\nRostdan ham o'chirilsinmi?", reply_markup=kb.as_markup()
    )


@router.message(AdminFlow.delete_movie_code)
async def movie_del_wrong(message: Message) -> None:
    await message.answer("Iltimos, faqat kino kodini (raqam) yuboring.", reply_markup=cancel_kb())


@router.callback_query(F.data.startswith("adm:m:del:"))
async def movie_del_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    movie_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        movie = await session.get(Movie, movie_id)
        if movie:
            title, code = movie.title, movie.code
            await session.delete(movie)
            await session.commit()
    await state.clear()
    text = f"✅ <b>{h(title)}</b> (kod: {code}) o'chirildi." if movie else "⚠️ Kino topilmadi."
    await callback.message.edit_text(text)
    await callback.answer()


# ---------- ✏️ Kino tahrirlash ----------

EDIT_FIELDS = {
    "title": "🎬 Nomi",
    "description": "📝 Tavsifi",
    "code": "🔢 Kodi",
    "file": "📁 Video/fayl",
}


@menu.message(F.text == kbs.BTN_MOVIE_EDIT)
async def movie_edit_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.edit_movie_code)
    await message.answer("✏️ <b>Kino tahrirlash</b>\n\nTahrirlanadigan kino kodini yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.edit_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def movie_edit_code(message: Message, state: FSMContext) -> None:
    movie = await get_movie(int(message.text))
    if movie is None:
        await message.answer(f"❌ {message.text} raqamli kino topilmadi. Boshqa kod yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(movie_id=movie.id)
    kb = InlineKeyboardBuilder()
    for key, label in EDIT_FIELDS.items():
        kb.button(text=label, callback_data=f"adm:me:{key}")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(2)
    await message.answer(
        f"{movie_caption(movie)}\n\n🔢 Kod: <b>{movie.code}</b> | 👁 {movie.views} marta ko'rilgan\n\n"
        "Nimani o'zgartiramiz?",
        reply_markup=kb.as_markup(),
    )


@router.message(AdminFlow.edit_movie_code)
async def movie_edit_wrong(message: Message) -> None:
    await message.answer("Iltimos, faqat kino kodini (raqam) yuboring.", reply_markup=cancel_kb())


@router.callback_query(F.data.startswith("adm:me:"))
async def movie_edit_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":")[-1]
    if field not in EDIT_FIELDS or not (await state.get_data()).get("movie_id"):
        await callback.answer("Qaytadan boshlang.", show_alert=True)
        return
    await state.update_data(edit_field=field)
    await state.set_state(AdminFlow.edit_movie_value)
    prompts = {
        "title": "Yangi nomni yuboring:",
        "description": 'Yangi tavsifni yuboring (o\'chirish uchun "-"):',
        "code": "Yangi kodni (raqam) yuboring:",
        "file": "Yangi video yoki faylni yuboring:",
    }
    await callback.message.answer(prompts[field], reply_markup=cancel_kb())
    await callback.answer()


@router.message(AdminFlow.edit_movie_value)
async def movie_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = data.get("edit_field")
    async with get_session() as session:
        movie = await session.get(Movie, data.get("movie_id"))
        if movie is None:
            await state.clear()
            await message.answer("⚠️ Kino topilmadi, ehtimol o'chirilgan.")
            return

        if field == "file":
            if message.video:
                movie.file_id, movie.file_type = message.video.file_id, "video"
            elif message.document:
                movie.file_id, movie.file_type = message.document.file_id, "document"
            else:
                await message.answer("Iltimos, video yoki fayl yuboring.", reply_markup=cancel_kb())
                return
        elif not message.text:
            await message.answer("Iltimos, matn yuboring.", reply_markup=cancel_kb())
            return
        elif field == "title":
            movie.title = message.text.strip()[:255]
        elif field == "description":
            movie.description = None if message.text.strip() == "-" else message.text.strip()
        elif field == "code":
            if not re.fullmatch(r"\d{1,9}", message.text.strip()):
                await message.answer("Iltimos, faqat raqam yuboring.", reply_markup=cancel_kb())
                return
            movie.code = int(message.text.strip())

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await message.answer("⚠️ Bu kod band. Boshqa kod yuboring:", reply_markup=cancel_kb())
            return
        code, title = movie.code, movie.title

    await state.clear()
    await message.answer(f"✅ Saqlandi!\n\n🎬 <b>{h(title)}</b> — kod: <b>{code}</b>")


# ---------- 📣 Kino postini yuborish ----------


@menu.message(F.text == kbs.BTN_MOVIE_POST)
async def movie_post_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.post_movie_code)
    await message.answer(
        "📣 <b>Kino postini yuborish</b>\n\n"
        "Kanalga e'lon qilinadigan kino kodini yuboring. Postda \"🎬 Kinoni ko'rish\" tugmasi bo'ladi — "
        "u botni ochadi va kinoni darhol beradi.",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.post_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def movie_post_code(message: Message, state: FSMContext) -> None:
    movie = await get_movie(int(message.text))
    if movie is None:
        await message.answer(f"❌ {message.text} raqamli kino topilmadi. Boshqa kod yuboring:", reply_markup=cancel_kb())
        return
    await state.update_data(post_code=movie.code)
    await state.set_state(AdminFlow.post_movie_photo)
    await message.answer(
        "🖼 Post uchun rasm (poster) yoki qisqa video yuboring.\n"
        'Rasmsiz, faqat matnli post uchun "-" yuboring.',
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.post_movie_code)
async def movie_post_wrong_code(message: Message) -> None:
    await message.answer("Iltimos, faqat kino kodini (raqam) yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.post_movie_photo)
async def movie_post_media(message: Message, state: FSMContext) -> None:
    if message.photo:
        await state.update_data(post_media=("photo", message.photo[-1].file_id))
    elif message.video:
        await state.update_data(post_media=("video", message.video.file_id))
    elif message.text and message.text.strip() == "-":
        await state.update_data(post_media=None)
    else:
        await message.answer('Iltimos, rasm/video yuboring yoki "-" yozing.', reply_markup=cancel_kb())
        return

    async with get_session() as session:
        channels = list((await session.execute(select(Channel))).scalars().all())
    kb = InlineKeyboardBuilder()
    for ch in channels:
        kb.button(text=f"📣 {(ch.title or str(ch.chat_id))[:30]}", callback_data=f"adm:mp:{ch.chat_id}")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(1)
    text = "Qaysi kanalga yuboramiz?"
    if not channels:
        text += "\n\n⚠️ Kanal qo'shilmagan. Avval 📣 Kanallarni sozlash bo'limida kanal qo'shing."
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("adm:mp:"))
async def movie_post_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    movie = await get_movie(data.get("post_code") or -1)
    if movie is None:
        await callback.answer("Kino topilmadi, qaytadan boshlang.", show_alert=True)
        return
    chat_id = int(callback.data.split(":")[-1])
    me = await callback.bot.me()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Kinoni ko'rish", url=f"https://t.me/{me.username}?start={movie.code}")]
        ]
    )
    caption = f"{movie_caption(movie)}\n\n🔢 Kino kodi: <b>{movie.code}</b>"
    media = data.get("post_media")
    try:
        if media and media[0] == "photo":
            await callback.bot.send_photo(chat_id, media[1], caption=caption, reply_markup=kb)
        elif media and media[0] == "video":
            await callback.bot.send_video(chat_id, media[1], caption=caption, reply_markup=kb)
        else:
            await callback.bot.send_message(chat_id, caption, reply_markup=kb)
    except Exception as exc:
        await callback.answer("Yuborib bo'lmadi", show_alert=True)
        await callback.message.answer(
            f"⚠️ Kanalga yuborib bo'lmadi: {h(str(exc))}\n\nBot kanalda admin va post yozish huquqi borligini tekshiring."
        )
        return
    await state.clear()
    await callback.message.edit_text(f"✅ Post kanalga yuborildi: 🎬 <b>{h(movie.title)}</b> (kod: {movie.code})")
    await callback.answer()


# ---------- 🎬 Shorts yuklash / o'chirish ----------


@menu.message(F.text == kbs.BTN_SHORT_ADD)
async def short_add_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_short_video)
    await message.answer(
        "🎬 <b>Shorts yuklash</b>\n\nQisqa videoni yuboring (izoh qo'shsangiz, u ham ko'rsatiladi).",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.add_short_video, F.video)
async def short_add_video(message: Message, state: FSMContext) -> None:
    await state.update_data(short_file_id=message.video.file_id, short_caption=message.caption)
    await state.set_state(AdminFlow.add_short_code)
    await message.answer(
        'Bu short qaysi kinoga tegishli? Kino kodini yuboring — ostida "🎬 To\'liq kino" tugmasi chiqadi.\n'
        'Tegishli kino bo\'lmasa "-" yuboring.',
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.add_short_video)
async def short_add_wrong(message: Message) -> None:
    await message.answer("Iltimos, video yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.add_short_code, F.text)
async def short_add_code(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    code = None
    if text != "-":
        if not re.fullmatch(r"\d{1,9}", text):
            await message.answer('Iltimos, kino kodini (raqam) yoki "-" yuboring.', reply_markup=cancel_kb())
            return
        if await get_movie(int(text)) is None:
            await message.answer(f"❌ {text} raqamli kino topilmadi. Boshqa kod yoki \"-\" yuboring:", reply_markup=cancel_kb())
            return
        code = int(text)
    data = await state.get_data()
    async with get_session() as session:
        short = Short(file_id=data["short_file_id"], caption=data.get("short_caption"), movie_code=code)
        session.add(short)
        await session.commit()
        short_id = short.id
    await state.clear()
    await message.answer(f"✅ Short qo'shildi (ID: {short_id})" + (f", kino kodi: {code}" if code else ""))


async def shorts_delete_view() -> tuple[str, InlineKeyboardMarkup]:
    async with get_session() as session:
        shorts = list((await session.execute(select(Short).order_by(Short.id.desc()).limit(40))).scalars().all())
    kb = InlineKeyboardBuilder()
    for s in shorts:
        label = (s.caption or "").strip().split("\n")[0][:25] or "izohsiz"
        code = f" | kod {s.movie_code}" if s.movie_code else ""
        kb.button(text=f"🗑 #{s.id} {label}{code}", callback_data=f"adm:sd:{s.id}")
    kb.adjust(1)
    text = "🗑 <b>Shorts o'chirish</b>\n\nO'chiriladigan shortni tanlang:" if shorts else "Hozircha shorts yo'q."
    return text, kb.as_markup()


@menu.message(F.text == kbs.BTN_SHORT_DEL)
async def short_del_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, kb = await shorts_delete_view()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("adm:sd:"))
async def short_del(callback: CallbackQuery) -> None:
    short_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        short = await session.get(Short, short_id)
        if short:
            await session.delete(short)
            await session.commit()
    await callback.answer("O'chirildi ✅")
    text, kb = await shorts_delete_view()
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass


# ---------- 💳 Karta sozlamalari ----------


@menu.message(F.text == kbs.BTN_CARD)
async def card_start(message: Message, state: FSMContext) -> None:
    number = await get_setting(CARD_NUMBER, "—")
    owner = await get_setting(CARD_OWNER, "—")
    price = await get_setting(PREMIUM_PRICE, "—")
    await state.set_state(AdminFlow.card_number)
    await message.answer(
        "💳 <b>Karta sozlamalari</b>\n\n"
        f"Karta raqami: <code>{h(number)}</code>\n"
        f"Karta egasi: <b>{h(owner)}</b>\n"
        f"Premium narxi: <b>{h(price)}</b>\n\n"
        'Yangi karta raqamini kiriting (o\'zgartirmaslik uchun "-"):',
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.card_number, F.text)
async def card_number(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if value != "-":
        digits = re.sub(r"\D", "", value)
        if not 12 <= len(digits) <= 19:
            await message.answer("⚠️ Karta raqami noto'g'ri. Qaytadan kiriting:", reply_markup=cancel_kb())
            return
        await state.update_data(card_number=" ".join(digits[i:i + 4] for i in range(0, len(digits), 4)))
    await state.set_state(AdminFlow.card_owner)
    await message.answer('Yangi karta egasining ismini kiriting (o\'zgartirmaslik uchun "-"):', reply_markup=cancel_kb())


@router.message(AdminFlow.card_owner, F.text)
async def card_owner(message: Message, state: FSMContext) -> None:
    value = message.text.strip()
    if value != "-":
        await state.update_data(card_owner=value[:100])
    await state.set_state(AdminFlow.premium_price)
    await message.answer(
        'Premium narxini kiriting, masalan: <code>30 kun — 15 000 so\'m</code> (o\'zgartirmaslik uchun "-"):',
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.premium_price, F.text)
async def card_price(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    value = message.text.strip()
    if data.get("card_number"):
        await set_setting(CARD_NUMBER, data["card_number"])
    if data.get("card_owner"):
        await set_setting(CARD_OWNER, data["card_owner"])
    if value != "-":
        await set_setting(PREMIUM_PRICE, value[:200])
    await state.clear()
    await message.answer("✅ Karta sozlamalari muvaffaqiyatli yangilandi!")


# ---------- 👤 Boshqarish (foydalanuvchi / admin) ----------


async def user_card(user_id: int, viewer_id: int) -> tuple[str, InlineKeyboardMarkup] | None:
    async with get_session() as session:
        u = await session.get(User, user_id)
    if u is None:
        return None
    premium = user_is_premium(u)
    lines = [
        f"👤 <b>{h(user_label(u))}</b>",
        f"ID: <code>{u.tg_id}</code>",
        f"Ism: {h(u.full_name or '—')}",
        f"Qo'shilgan: {fmt_date(u.joined_at)}",
        f"Holat: {'🚫 bloklangan' if u.is_blocked else '✅ faol'}",
        f"Premium: {'💎 ' + fmt_date(u.premium_until) + ' gacha' if premium else 'yo‘q'}",
        f"Admin: {'👑 ha' if is_admin(u.tg_id) else 'yo‘q'}",
    ]
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Blokdan chiqarish" if u.is_blocked else "🚫 Bloklash", callback_data=f"adm:u:block:{u.tg_id}")
    kb.button(text="💎 Premium berish", callback_data=f"adm:u:prem:{u.tg_id}")
    if premium:
        kb.button(text="❌ Premiumni olish", callback_data=f"adm:u:unprem:{u.tg_id}")
    if is_super_admin(viewer_id) and not is_super_admin(u.tg_id):
        if is_admin(u.tg_id):
            kb.button(text="👑 Adminlikdan olish", callback_data=f"adm:u:unadmin:{u.tg_id}")
        else:
            kb.button(text="👑 Admin qilish", callback_data=f"adm:u:admin:{u.tg_id}")
    kb.adjust(2)
    return "\n".join(lines), kb.as_markup()


@menu.message(F.text == kbs.BTN_MANAGE)
async def manage_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.manage_user_id)
    await message.answer(
        "👤 <b>Boshqarish</b>\n\n"
        "Foydalanuvchining Telegram ID raqamini yuboring (yoki uning xabarini forward qiling).\n"
        "Keyin uni bloklash, premium berish yoki admin qilish mumkin.\n\n"
        "💡 Foydalanuvchi o'z ID sini botga /myid yuborib bilishi mumkin.",
        reply_markup=cancel_kb(),
    )


@router.message(AdminFlow.manage_user_id)
async def manage_user(message: Message, state: FSMContext) -> None:
    user_id = None
    origin = message.forward_origin
    if origin is not None and origin.type == MessageOriginType.USER:
        user_id = origin.sender_user.id
    elif message.text and re.fullmatch(r"\d{3,15}", message.text.strip()):
        user_id = int(message.text.strip())
    if user_id is None:
        await message.answer("Iltimos, ID raqam yuboring yoki foydalanuvchi xabarini forward qiling.", reply_markup=cancel_kb())
        return
    card = await user_card(user_id, message.from_user.id)
    if card is None:
        await message.answer(
            "❌ Bu foydalanuvchi botda topilmadi (u avval botga /start bosishi kerak). Boshqa ID yuboring:",
            reply_markup=cancel_kb(),
        )
        return
    await state.clear()
    await message.answer(card[0], reply_markup=card[1])


@router.callback_query(F.data.startswith("adm:u:"))
async def manage_action(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, action, raw_id = callback.data.split(":")
    user_id = int(raw_id)
    viewer = callback.from_user.id
    note = "✅ Bajarildi"

    if action == "block":
        if is_admin(user_id):
            await callback.answer("Adminni bloklab bo'lmaydi.", show_alert=True)
            return
        async with get_session() as session:
            u = await session.get(User, user_id)
            if u:
                u.is_blocked = not u.is_blocked
                await session.commit()
    elif action == "prem":
        await state.set_state(AdminFlow.approve_days)
        await state.update_data(premium_user_id=user_id, payment_id=None)
        await callback.message.answer("💎 Necha kunlik premium berilsin? Kun sonini yuboring (masalan 30):", reply_markup=cancel_kb())
        await callback.answer()
        return
    elif action == "unprem":
        await revoke_premium(user_id)
    elif action in ("admin", "unadmin"):
        if not is_super_admin(viewer):
            await callback.answer("Faqat asosiy admin adminlarni boshqara oladi.", show_alert=True)
            return
        if action == "admin":
            await add_admin(user_id, viewer)
            note = "👑 Admin qilindi"
            try:
                await callback.bot.send_message(
                    user_id, "👑 Siz botga admin qilindingiz! /admin buyrug'i orqali admin panelni oching."
                )
            except Exception:
                pass
        else:
            await remove_admin(user_id)
            note = "Adminlikdan olindi"

    await callback.answer(note)
    card = await user_card(user_id, viewer)
    if card:
        try:
            await callback.message.edit_text(card[0], reply_markup=card[1])
        except Exception:
            pass


# ---------- 👑 Adminlar ro'yxati ----------


@menu.message(F.text == kbs.BTN_ADMINS)
async def admins_list(message: Message, state: FSMContext) -> None:
    await state.clear()
    ids = sorted(all_admin_ids())
    async with get_session() as session:
        users = {u.tg_id: u for u in (await session.execute(select(User).where(User.tg_id.in_(ids)))).scalars()}
    lines = []
    for i, admin_id in enumerate(ids, 1):
        u = users.get(admin_id)
        name = h(user_label(u)) if u else "—"
        role = "asosiy" if admin_id in settings.ADMIN_IDS else "qo'shilgan"
        lines.append(f"{i}. {name} — <code>{admin_id}</code> ({role})")
    await message.answer(
        "👑 <b>Adminlar ro'yxati</b>\n\n" + ("\n".join(lines) or "Admin yo'q")
        + "\n\n<i>Asosiy adminlar Railway'dagi ADMIN_IDS sozlamasida. Qo'shimcha admin qo'shish: "
        "👤 Boshqarish → ID → 👑 Admin qilish.</i>"
    )


# ---------- 💎 Premiumlar ro'yxati ----------


@menu.message(F.text == kbs.BTN_PREMIUMS)
async def premiums_list(message: Message, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        users = list(
            (
                await session.execute(
                    select(User).where(User.premium_until > utcnow()).order_by(User.premium_until).limit(100)
                )
            ).scalars()
        )
    lines = [f"{i}. {h(user_label(u))} — <code>{u.tg_id}</code> — {fmt_date(u.premium_until)} gacha" for i, u in enumerate(users, 1)]
    await message.answer(
        f"💎 <b>Premiumlar ro'yxati</b> ({len(users)} ta)\n\n" + ("\n".join(lines) or "Hozircha premium foydalanuvchi yo'q.")
    )


# ---------- 🔄 Premium holati ----------


async def premium_status_view() -> tuple[str, InlineKeyboardMarkup]:
    enabled = await premium_enabled()
    async with get_session() as session:
        pending = (await session.execute(select(func.count(Payment.id)).where(Payment.status == "pending"))).scalar_one()
        approved = (await session.execute(select(func.count(Payment.id)).where(Payment.status == "approved"))).scalar_one()
        active = (await session.execute(select(func.count(User.tg_id)).where(User.premium_until > utcnow()))).scalar_one()
    card_ok = bool(await get_setting(CARD_NUMBER))
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Premiumni o'chirish" if enabled else "✅ Premiumni yoqish", callback_data="adm:prem:toggle")
    if pending:
        kb.button(text=f"💳 Kutilayotgan to'lovlar ({pending})", callback_data="adm:prem:pending")
    kb.adjust(1)
    text = (
        "🔄 <b>Premium holati</b>\n\n"
        f"Holat: {'✅ yoqilgan' if enabled else '❌ o‘chirilgan'}\n"
        f"💎 Faol premiumlar: {active}\n"
        f"💳 Kutilayotgan to'lovlar: {pending}\n"
        f"✅ Tasdiqlangan to'lovlar: {approved}\n"
        + ("" if card_ok else "\n⚠️ Karta kiritilmagan — 💳 Karta sozlamalari bo'limida kiriting.")
        + "\n\n<i>Premium foydalanuvchilar majburiy kanallarga obuna bo'lmasdan kinolarni oladi.</i>"
    )
    return text, kb.as_markup()


@menu.message(F.text == kbs.BTN_PREMIUM_STATUS)
async def premium_status(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, kb = await premium_status_view()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm:prem:toggle")
async def premium_toggle(callback: CallbackQuery) -> None:
    await set_setting(PREMIUM_ENABLED, "0" if await premium_enabled() else "1")
    await callback.answer("Saqlandi ✅")
    text, kb = await premium_status_view()
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "adm:prem:pending")
async def premium_pending(callback: CallbackQuery) -> None:
    async with get_session() as session:
        payments = list(
            (await session.execute(select(Payment).where(Payment.status == "pending").order_by(Payment.id).limit(10))).scalars()
        )
    await callback.answer()
    for p in payments:
        await send_payment_to_admin(callback.bot, callback.from_user.id, p)


# ---------- To'lovlarni tasdiqlash ----------


def payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"pay:ok:{payment_id}")
    kb.button(text="❌ Rad etish", callback_data=f"pay:no:{payment_id}")
    return kb.as_markup()


async def send_payment_to_admin(bot, admin_id: int, payment: Payment) -> None:
    async with get_session() as session:
        u = await session.get(User, payment.user_id)
    label = h(user_label(u)) if u else "—"
    await bot.send_photo(
        admin_id,
        payment.photo_file_id,
        caption=(
            f"💳 <b>Yangi to'lov cheki #{payment.id}</b>\n\n"
            f"👤 {label}\nID: <code>{payment.user_id}</code>\n🕒 {fmt_date(payment.created_at)}"
        ),
        reply_markup=payment_kb(payment.id),
    )


@router.callback_query(F.data.startswith("pay:"))
async def payment_decision(callback: CallbackQuery, state: FSMContext) -> None:
    _, decision, raw_id = callback.data.split(":")
    async with get_session() as session:
        payment = await session.get(Payment, int(raw_id))
        if payment is None or payment.status != "pending":
            await callback.answer("Bu to'lov allaqachon ko'rib chiqilgan.", show_alert=True)
            return
        if decision == "no":
            payment.status = "rejected"
            await session.commit()
    if decision == "no":
        try:
            await callback.bot.send_message(
                payment.user_id,
                "❌ To'lovingiz tasdiqlanmadi. Savollar bo'lsa, admin bilan bog'laning yoki chekni qayta yuboring.",
            )
        except Exception:
            pass
        await callback.message.edit_caption(caption=(callback.message.caption or "") + "\n\n❌ Rad etildi")
        await callback.answer("Rad etildi")
        return

    await state.set_state(AdminFlow.approve_days)
    await state.update_data(premium_user_id=payment.user_id, payment_id=payment.id)
    await callback.message.answer(
        f"💎 To'lov #{payment.id}: necha kunlik premium berilsin? Kun sonini yuboring (masalan 30):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminFlow.approve_days, F.text.regexp(r"^\d{1,4}$"))
async def approve_days(message: Message, state: FSMContext) -> None:
    days = int(message.text)
    if days <= 0:
        await message.answer("Kun soni 0 dan katta bo'lishi kerak:", reply_markup=cancel_kb())
        return
    data = await state.get_data()
    user_id = data.get("premium_user_id")
    until = await grant_premium(user_id, days)
    if until is None:
        await state.clear()
        await message.answer("⚠️ Foydalanuvchi topilmadi.")
        return
    if data.get("payment_id"):
        async with get_session() as session:
            payment = await session.get(Payment, data["payment_id"])
            if payment:
                payment.status, payment.days = "approved", days
                await session.commit()
    await state.clear()
    try:
        await message.bot.send_message(
            user_id,
            f"💎 <b>Premium faollashtirildi!</b>\n\n{fmt_date(until)} gacha kanallarga obuna bo'lmasdan "
            "barcha kinolarni olishingiz mumkin. Rahmat! 🎬",
        )
    except Exception:
        pass
    await message.answer(f"✅ Premium berildi: <code>{user_id}</code> — {fmt_date(until)} gacha")


@router.message(AdminFlow.approve_days)
async def approve_days_wrong(message: Message) -> None:
    await message.answer("Iltimos, kun sonini raqam bilan yuboring (masalan 30):", reply_markup=cancel_kb())
