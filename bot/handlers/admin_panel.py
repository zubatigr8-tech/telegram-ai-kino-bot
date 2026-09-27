"""Telegram ichidagi admin panel — faqat ADMIN_IDS'dagilar uchun.
Veb-admin paneldagi asosiy bo'limlarni (statistika, foydalanuvchilar, kinolar,
kanallar, xabar yuborish) botning o'zida, inline tugmalar orqali boshqaradi."""
import re
from html import escape as h

from aiogram import F, Router
from aiogram.enums import MessageOriginType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from bot.channels import ChannelError, channel_url, clean_username, fetch_channel_info
from bot.states import AdminFlow
from shared.config import settings
from shared.db.database import get_session
from shared.db.models import BroadcastJob, Channel, MediaCache, Movie, SongCache, User

router = Router(name="admin_panel")
router.message.filter(F.from_user.id.in_(settings.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(settings.ADMIN_IDS))

USERS_PAGE_SIZE = 8
MOVIES_PAGE_SIZE = 30


def main_admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Statistika", callback_data="adm:stats")
    kb.button(text="👤 Foydalanuvchilar", callback_data="adm:users")
    kb.button(text="🎬 Kinolar", callback_data="adm:movies")
    kb.button(text="📢 Kanallar", callback_data="adm:channels")
    kb.button(text="🔔 Xabar yuborish", callback_data="adm:broadcast")
    kb.adjust(1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Orqaga", callback_data="adm:menu")
    return kb.as_markup()


def cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    return kb.as_markup()


@router.message(Command("admin"))
async def admin_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("⚙️ <b>Admin panel</b>\n\nBo'limni tanlang:", reply_markup=main_admin_kb())


@router.callback_query(F.data == "adm:menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("⚙️ <b>Admin panel</b>\n\nBo'limni tanlang:", reply_markup=main_admin_kb())
    await callback.answer()


@router.callback_query(F.data == "adm:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.\n\n⚙️ <b>Admin panel</b>", reply_markup=main_admin_kb())
    await callback.answer()


# ---------- Statistika ----------


@router.callback_query(F.data == "adm:stats")
async def cb_stats(callback: CallbackQuery) -> None:
    async with get_session() as session:
        total_users = (await session.execute(select(func.count(User.tg_id)))).scalar_one()
        blocked = (
            await session.execute(select(func.count(User.tg_id)).where(User.is_blocked == True))  # noqa: E712
        ).scalar_one()
        total_movies = (await session.execute(select(func.count(Movie.id)))).scalar_one()
        total_channels = (await session.execute(select(func.count(Channel.id)))).scalar_one()
        pending = (
            await session.execute(
                select(func.count(BroadcastJob.id)).where(BroadcastJob.status.in_(("pending", "sending")))
            )
        ).scalar_one()
        total_sent = (await session.execute(select(func.sum(BroadcastJob.sent_count)))).scalar_one() or 0
        total_downloads = (await session.execute(select(func.sum(MediaCache.requests)))).scalar_one() or 0
        total_songs = (
            await session.execute(select(func.count(SongCache.song_key)).where(SongCache.audio_file_id.is_not(None)))
        ).scalar_one()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"✅ Faol: <b>{total_users - blocked}</b>\n"
        f"🚫 Bloklangan: <b>{blocked}</b>\n"
        f"🎬 Kinolar soni: <b>{total_movies}</b>\n"
        f"📢 Majburiy kanallar: <b>{total_channels}</b>\n"
        f"⏳ Navbatdagi xabarlar: <b>{pending}</b>\n"
        f"📨 Jami yuborilgan xabarlar: <b>{total_sent}</b>\n"
        f"📥 Yuklangan videolar: <b>{total_downloads}</b>\n"
        f"🎵 Topilgan qo'shiqlar: <b>{total_songs}</b>"
    )
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()


# ---------- Foydalanuvchilar ----------


async def render_users(callback: CallbackQuery) -> None:
    async with get_session() as session:
        total = (await session.execute(select(func.count(User.tg_id)))).scalar_one()
        blocked = (
            await session.execute(select(func.count(User.tg_id)).where(User.is_blocked == True))  # noqa: E712
        ).scalar_one()
        result = await session.execute(select(User).order_by(User.joined_at.desc()).limit(USERS_PAGE_SIZE))
        users = list(result.scalars().all())

    lines = [f"👤 <b>Foydalanuvchilar</b>\n\nJami: {total} | Faol: {total - blocked} | Bloklangan: {blocked}\n"]
    kb = InlineKeyboardBuilder()
    for u in users:
        label = f"@{u.username}" if u.username else (u.full_name or str(u.tg_id))
        status = "🚫" if u.is_blocked else "✅"
        lines.append(f"{status} {h(label)} — <code>{u.tg_id}</code>")
        btn_text = "Blokdan chiqarish" if u.is_blocked else "Bloklash"
        kb.button(text=f"{btn_text}: {label[:15]}", callback_data=f"adm:u:t:{u.tg_id}")
    kb.adjust(1)
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:menu"))

    text = "\n".join(lines) + f"\n\n(So'nggi {len(users)} ta ko'rsatildi)"
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "adm:users")
async def cb_users(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_users(callback)


@router.callback_query(F.data.startswith("adm:u:t:"))
async def cb_toggle_user(callback: CallbackQuery) -> None:
    tg_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        user = await session.get(User, tg_id)
        if user:
            user.is_blocked = not user.is_blocked
            await session.commit()
    await callback.answer("Holat o'zgartirildi ✅")
    await render_users(callback)


# ---------- Kinolar ----------


@router.callback_query(F.data == "adm:movies")
async def cb_movies(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    async with get_session() as session:
        result = await session.execute(select(Movie).order_by(Movie.code).limit(MOVIES_PAGE_SIZE))
        movies = list(result.scalars().all())
        total = (await session.execute(select(func.count(Movie.id)))).scalar_one()

    if movies:
        body = "\n".join(f"<b>{m.code}</b> — {h(m.title)}" for m in movies)
    else:
        body = "Hozircha kino qo'shilmagan."

    text = f"🎬 <b>Kinolar</b> (jami: {total})\n\n{body}"
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Yangi kino qo'shish", callback_data="adm:m:add")
    kb.button(text="🗑 Kino o'chirish", callback_data="adm:m:del")
    kb.button(text="⬅️ Orqaga", callback_data="adm:menu")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "adm:m:add")
async def cb_add_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_movie_file)
    await callback.message.edit_text(
        "🎬 <b>Yangi kino qo'shish</b>\n\nAvval kino videosi yoki faylini yuboring.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminFlow.add_movie_file, F.video | F.document)
async def add_movie_receive_file(message: Message, state: FSMContext) -> None:
    if message.video:
        file_id, file_type = message.video.file_id, "video"
    else:
        file_id, file_type = message.document.file_id, "document"
    await state.update_data(file_id=file_id, file_type=file_type)
    await state.set_state(AdminFlow.add_movie_code)
    await message.answer("Endi kino kodini (raqam) yuboring:", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_file)
async def add_movie_wrong_file(message: Message) -> None:
    await message.answer("Iltimos, video yoki fayl yuboring.", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def add_movie_receive_code(message: Message, state: FSMContext) -> None:
    code = int(message.text)
    async with get_session() as session:
        existing = await session.execute(select(Movie).where(Movie.code == code))
        if existing.scalar_one_or_none() is not None:
            await message.answer(f"⚠️ Kod {code} band. Boshqa raqam yuboring:", reply_markup=cancel_kb())
            return
    await state.update_data(code=code)
    await state.set_state(AdminFlow.add_movie_title)
    await message.answer("Kino nomini yuboring:", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_code)
async def add_movie_wrong_code(message: Message) -> None:
    await message.answer("Iltimos, faqat raqam yuboring (ko'pi bilan 9 xonali).", reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_title, F.text)
async def add_movie_receive_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip()[:255])
    await state.set_state(AdminFlow.add_movie_description)
    await message.answer('Tavsif yuboring (yoki "-" deb yozib o\'tkazib yuboring):', reply_markup=cancel_kb())


@router.message(AdminFlow.add_movie_description, F.text)
async def add_movie_receive_description(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    description = None if message.text.strip() == "-" else message.text

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
            # Shu orada kod boshqa joyda (masalan veb-panelda) band qilingan
            await session.rollback()
            await state.set_state(AdminFlow.add_movie_code)
            await message.answer(
                f"⚠️ Kod {data['code']} band bo'lib qoldi. Boshqa kod yuboring:", reply_markup=cancel_kb()
            )
            return

    await state.clear()
    await message.answer(
        f"✅ Kino qo'shildi!\n\n🎬 <b>{h(data['title'])}</b> — kod: <b>{data['code']}</b>",
        reply_markup=main_admin_kb(),
    )


@router.callback_query(F.data == "adm:m:del")
async def cb_delete_movie_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.delete_movie_code)
    await callback.message.edit_text(
        "🗑 <b>Kino o'chirish</b>\n\nO'chirish uchun kino kodini (raqamini) yuboring.",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminFlow.delete_movie_code, F.text.regexp(r"^\d{1,9}$"))
async def delete_movie_receive_code(message: Message, state: FSMContext) -> None:
    code = int(message.text)
    async with get_session() as session:
        result = await session.execute(select(Movie).where(Movie.code == code))
        movie = result.scalar_one_or_none()

    if movie is None:
        await message.answer(f"❌ {code} raqamli kino topilmadi. Boshqa kod yuboring:", reply_markup=cancel_kb())
        return

    await state.update_data(movie_id=movie.id, movie_title=movie.title, movie_code=movie.code)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, o'chirilsin", callback_data="adm:m:del:confirm")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(1)
    await message.answer(
        f"🎬 <b>{h(movie.title)}</b> (kod: {movie.code})\n\nRostdan ham o'chirilsinmi?",
        reply_markup=kb.as_markup(),
    )


@router.message(AdminFlow.delete_movie_code)
async def delete_movie_wrong_code(message: Message) -> None:
    await message.answer("Iltimos, faqat kino kodini (raqam) yuboring.", reply_markup=cancel_kb())


@router.callback_query(F.data == "adm:m:del:confirm")
async def cb_delete_movie_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    movie_id = data.get("movie_id")

    async with get_session() as session:
        movie = await session.get(Movie, movie_id) if movie_id else None
        if movie:
            await session.delete(movie)
            await session.commit()

    await state.clear()
    if movie:
        text = f"✅ <b>{h(data['movie_title'])}</b> (kod: {data['movie_code']}) o'chirildi."
    else:
        text = "⚠️ Kino topilmadi, ehtimol allaqachon o'chirilgan."
    await callback.message.edit_text(text, reply_markup=back_kb())
    await callback.answer()


# ---------- Kanallar ----------


async def render_channels(callback: CallbackQuery) -> None:
    async with get_session() as session:
        result = await session.execute(select(Channel))
        channels = list(result.scalars().all())

    if channels:
        lines = []
        for c in channels:
            status = "✅" if c.is_active else "🚫"
            url = channel_url(c) or "⚠️ havola yo'q"
            lines.append(f"{status} {h(c.title or str(c.chat_id))}\n    ID: <code>{c.chat_id}</code> | {h(url)}")
        body = "\n".join(lines)
    else:
        body = "Hozircha kanal qo'shilmagan (obuna tekshiruvi o'chirilgan)."

    kb = InlineKeyboardBuilder()
    for c in channels:
        toggle_label = "O'chirish" if c.is_active else "Yoqish"
        label = (c.title or str(c.chat_id))[:20]
        kb.row(
            InlineKeyboardButton(text=f"🔄 {toggle_label}: {label}", callback_data=f"adm:c:t:{c.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"adm:c:d:{c.id}"),
        )
    kb.row(InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="adm:c:add"))
    kb.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:menu"))

    text = f"📢 <b>Majburiy kanallar</b>\n\n{body}"
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "adm:channels")
async def cb_channels(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await render_channels(callback)


@router.callback_query(F.data.startswith("adm:c:t:"))
async def cb_toggle_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = not channel.is_active
            await session.commit()
    await callback.answer("Holat o'zgartirildi ✅")
    await render_channels(callback)


@router.callback_query(F.data.startswith("adm:c:d:"))
async def cb_delete_channel(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            await session.delete(channel)
            await session.commit()
    await callback.answer("O'chirildi ✅")
    await render_channels(callback)


@router.callback_query(F.data == "adm:c:add")
async def cb_add_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_channel_chatid)
    await callback.message.edit_text(
        "📢 <b>Yangi kanal qo'shish</b>\n\n"
        "1️⃣ Avval botni kanalga <b>admin</b> qilib qo'shing.\n"
        "2️⃣ Keyin shu yerga quyidagilardan birini yuboring:\n"
        "• kanaldan istalgan postni <b>forward</b> qiling (eng oson yo'l);\n"
        "• kanal ID raqami, masalan <code>-1001234567890</code>;\n"
        "• ochiq kanal bo'lsa — <code>@username</code>.\n\n"
        "Kanal nomi, havolasi (yopiq kanal uchun taklif havolasi) bot tomonidan avtomatik olinadi.",
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
        f"✅ Kanal qo'shildi!\n\n📢 <b>{h(info['title'] or str(info['chat_id']))}</b>\n"
        f"ID: <code>{info['chat_id']}</code>\nHavola: {h(link)}",
        reply_markup=main_admin_kb(),
        disable_web_page_preview=True,
    )


# ---------- Xabar yuborish ----------


@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.broadcast_text)
    await callback.message.edit_text(
        "🔔 <b>Barchaga xabar yuborish</b>\n\nXabar matnini yozing:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminFlow.broadcast_text, F.text)
async def broadcast_receive_text(message: Message, state: FSMContext) -> None:
    # html_text — admin qo'ygan qalin/kursiv formatlash saqlanadi, "<" kabi belgilar esa
    # to'g'ri ekranlanadi (aks holda HTML rejimida xabar hech kimga yetib bormaydi)
    await state.update_data(text=message.html_text)
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Yuborish", callback_data="adm:b:send")
    kb.button(text="❌ Bekor qilish", callback_data="adm:cancel")
    kb.adjust(1)
    await message.answer(
        f"Quyidagi xabar <b>barcha</b> foydalanuvchilarga yuboriladi:\n\n{message.html_text}\n\nTasdiqlaysizmi?",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data == "adm:b:send")
async def cb_broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("text")
    if text:
        async with get_session() as session:
            session.add(BroadcastJob(text=text))
            await session.commit()
    await state.clear()
    await callback.message.edit_text(
        "✅ Xabar navbatga qo'yildi, tez orada barcha foydalanuvchilarga yuboriladi.",
        reply_markup=back_kb(),
    )
    await callback.answer()
