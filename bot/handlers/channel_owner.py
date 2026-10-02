"""Kanal admini (egasi) bo'limi: o'z kanali statistikasi va zayavkalarni bitta tugma bilan tasdiqlash.
Bot adminlari ham shu tugmalardan foydalana oladi."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.join_requests import approve_kb, can_manage, channel_stats_text, owned_channels, request_counts, start_approve_all
from bot.keyboards import BTN_MY_CHANNEL
from shared.db.database import get_session
from shared.db.models import Channel

router = Router(name="channel_owner")


@router.message(Command("kanal"))
@router.message(F.text == BTN_MY_CHANNEL)
async def my_channels(message: Message) -> None:
    channels = await owned_channels(message.from_user.id)
    if not channels:
        await message.answer("Sizga biriktirilgan kanal yo'q. Bu bo'lim faqat kanal adminlari uchun.")
        return
    for ch in channels:
        pending, _, _ = await request_counts(ch.chat_id)
        await message.answer(await channel_stats_text(message.bot, ch), reply_markup=approve_kb(ch, pending))


async def _load(callback: CallbackQuery) -> Channel | None:
    async with get_session() as session:
        channel = await session.get(Channel, int(callback.data.split(":")[-1]))
    if channel is None:
        await callback.answer("Kanal topilmadi.", show_alert=True)
        return None
    if not can_manage(callback.from_user.id, channel):
        await callback.answer("Bu kanalni boshqarish huquqingiz yo'q.", show_alert=True)
        return None
    return channel


@router.callback_query(F.data.startswith("jr:view:"))
async def view_channel(callback: CallbackQuery) -> None:
    channel = await _load(callback)
    if channel is None:
        return
    pending, _, _ = await request_counts(channel.chat_id)
    await callback.answer("Yangilandi")
    try:
        await callback.message.edit_text(
            await channel_stats_text(callback.bot, channel), reply_markup=approve_kb(channel, pending)
        )
    except Exception:
        pass  # o'zgarish bo'lmasa "message is not modified"


@router.callback_query(F.data.startswith("jr:all:"))
async def approve_all(callback: CallbackQuery) -> None:
    channel = await _load(callback)
    if channel is None:
        return
    pending, _, _ = await request_counts(channel.chat_id)
    if not pending:
        await callback.answer("Tasdiq kutayotgan zayavka yo'q.", show_alert=True)
        return
    if not start_approve_all(callback.bot, channel, callback.from_user.id):
        await callback.answer("Tasdiqlash allaqachon ketmoqda, kuting.", show_alert=True)
        return
    minutes = max(1, round(pending * 0.08 / 60))
    await callback.answer("Tasdiqlash boshlandi ✅")
    await callback.message.answer(
        f"🔄 <b>{pending}</b> ta zayavka tasdiqlanmoqda (taxminan {minutes} daqiqa). Tugagach xabar beraman."
    )
