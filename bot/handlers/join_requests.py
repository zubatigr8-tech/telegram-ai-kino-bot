"""Kanal/guruhga qo'shilish so'rovlari (zayavkalar).

Bot admin bo'lgan (va "Foydalanuvchilarni qo'shish" huquqi berilgan) kanalga kimdir
so'rov yuborsa:
1. Bot unga shaxsiy xabar yuboradi (Telegram bunga faqat so'rov ko'rib chiqilguncha ruxsat beradi);
2. So'rovni avtomatik tasdiqlaydi."""
import logging
from html import escape as h

from aiogram import Router
from aiogram.types import ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup

from shared.config import settings
from shared.db.database import get_session
from shared.db.models import JoinRequest

logger = logging.getLogger(__name__)
router = Router(name="join_requests")


def _start_keyboard(username: str | None) -> InlineKeyboardMarkup | None:
    if not username:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Botni ishga tushirish", url=f"https://t.me/{username}?start=join")
    ]])


@router.chat_join_request()
async def on_join_request(request: ChatJoinRequest) -> None:
    if not settings.AUTO_APPROVE_JOIN_REQUESTS:
        return

    user = request.from_user
    chat_title = request.chat.title or "Kanal"
    me = await request.bot.me()

    # Xabarni tasdiqlashdan OLDIN yuboramiz: so'rov ko'rib chiqilgach, bot bu foydalanuvchiga
    # (u botni /start qilmagan bo'lsa) yoza olmaydi
    message_sent = False
    text = settings.JOIN_WELCOME_TEXT.format(name=h(user.first_name or "do'st"), chat=h(chat_title))
    try:
        await request.bot.send_message(
            request.user_chat_id, text, reply_markup=_start_keyboard(me.username)
        )
        message_sent = True
    except Exception as exc:
        logger.info("Zayavka egasiga xabar yuborilmadi (%s): %s", user.id, exc)

    approved = False
    try:
        await request.approve()
        approved = True
    except Exception as exc:
        # Ko'pincha sabab: botda "Foydalanuvchilarni qo'shish" (Invite users) huquqi yo'q
        logger.warning("Zayavkani tasdiqlab bo'lmadi (chat=%s, user=%s): %s", request.chat.id, user.id, exc)

    async with get_session() as session:
        session.add(JoinRequest(
            user_id=user.id, chat_id=request.chat.id, chat_title=chat_title[:255],
            approved=approved, message_sent=message_sent,
        ))
        await session.commit()
