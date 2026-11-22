"""Kanal/guruhga qo'shilish so'rovlari (zayavkalar).

MUHIM: bot zayavkalarni O'ZI TASDIQLAMAYDI. Bot admin bo'lgan (va "Foydalanuvchilarni qo'shish"
huquqi berilgan) kanalga kimdir so'rov yuborsa:
1. Bot unga shaxsiy xabar yuboradi (Telegram bunga faqat so'rov ko'rib chiqilguncha ruxsat beradi);
2. So'rovni bazaga yozib qo'yadi;
3. Kutilayotgan zayavkalar 1000, 5000, 10000, 20000, ... ga yetganda adminlarga xabar beradi.

Admin /zayavkalar buyrug'i (yoki /admin → 📨 Zayavkalar) orqali kanalni tanlab, hammasini birdaniga
tasdiqlaydi. Bot admin bo'lishidan OLDIN kelgan zayavkalarni Telegram botga ko'rsatmaydi —
ular uchun tools/approve_all_join_requests.py skripti bor."""
import asyncio
import logging
from html import escape as h

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select, update

from shared.config import settings
from shared.db.database import get_session
from shared.db.models import JoinRequest

logger = logging.getLogger(__name__)
router = Router(name="join_requests")
router.message.filter(F.from_user.id.in_(settings.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(settings.ADMIN_IDS))

APPROVE_DELAY = 0.05  # Telegram flood limitiga tushmaslik uchun (≈20 ta/soniya, 10 000 ta ≈ 9 daqiqa)
BATCH_SIZE = 200
PROGRESS_EVERY = 500
# So'rov yo'q bo'lib ketgan (foydalanuvchi bekor qilgan / allaqachon ko'rib chiqilgan) — keyingisiga o'tamiz
_GONE_ERRORS = ("HIDE_REQUESTER_MISSING", "USER_CHANNELS_TOO_MUCH", "INPUT_USER_DEACTIVATED", "USER_DEACTIVATED")
_PENDING = (JoinRequest.approved == False, JoinRequest.failed == False)  # noqa: E712

_running: set[int] = set()  # hozir tasdiqlanayotgan kanallar (chat_id)
_tasks: set[asyncio.Task] = set()  # fon vazifalari yig'ishtirib tashlanmasligi uchun


def next_milestone_hit(pending: int) -> bool:
    """1000, 5000, 10000, 20000, 30000 ... — kutilayotganlar soni aynan shu songa yetganda bildiramiz."""
    return pending in (1000, 5000) or (pending >= 10000 and pending % 10000 == 0)


def _start_keyboard(username: str | None) -> InlineKeyboardMarkup | None:
    if not username:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Botni ishga tushirish", url=f"https://t.me/{username}?start=join")
    ]])


# ---------- Zayavkalarni yig'ish ----------

async def _has_pending(user_id: int, chat_id: int) -> bool:
    async with get_session() as session:
        row = await session.execute(
            select(JoinRequest.id).where(JoinRequest.user_id == user_id, JoinRequest.chat_id == chat_id, *_PENDING).limit(1)
        )
        return row.first() is not None


async def pending_count(chat_id: int) -> int:
    async with get_session() as session:
        stmt = select(func.count(JoinRequest.id)).where(JoinRequest.chat_id == chat_id, *_PENDING)
        return (await session.execute(stmt)).scalar_one()


async def pending_by_chat() -> list[tuple[int, str, int]]:
    """[(chat_id, kanal nomi, kutilayotganlar soni)] — eng ko'pi birinchi."""
    async with get_session() as session:
        rows = await session.execute(
            select(JoinRequest.chat_id, func.max(JoinRequest.chat_title), func.count(JoinRequest.id))
            .where(*_PENDING)
            .group_by(JoinRequest.chat_id)
            .order_by(func.count(JoinRequest.id).desc())
        )
        return [(chat_id, title or str(chat_id), count) for chat_id, title, count in rows]


async def _notify_admins(bot: Bot, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception:
            pass  # admin botni /start qilmagan bo'lishi mumkin


@router.chat_join_request()
async def on_join_request(request: ChatJoinRequest) -> None:
    user = request.from_user
    chat_title = request.chat.title or "Kanal"
    if await _has_pending(user.id, request.chat.id):
        return  # bu so'rov allaqachon yozib qo'yilgan

    # Xabarni hozir yuboramiz: so'rov ko'rib chiqilgach, bot bu foydalanuvchiga
    # (u botni /start qilmagan bo'lsa) yoza olmaydi
    message_sent = False
    if settings.JOIN_WELCOME_TEXT.strip():
        me = await request.bot.me()
        text = settings.JOIN_WELCOME_TEXT.format(name=h(user.first_name or "do'st"), chat=h(chat_title))
        try:
            await request.bot.send_message(request.user_chat_id, text, reply_markup=_start_keyboard(me.username))
            message_sent = True
        except Exception as exc:
            logger.info("Zayavka egasiga xabar yuborilmadi (%s): %s", user.id, exc)

    async with get_session() as session:
        session.add(JoinRequest(
            user_id=user.id, chat_id=request.chat.id, chat_title=chat_title[:255],
            approved=False, message_sent=message_sent,
        ))
        await session.commit()

    pending = await pending_count(request.chat.id)
    if next_milestone_hit(pending):
        await _notify_admins(
            request.bot,
            f"🎉 <b>{h(chat_title)}</b> kanalida <b>{pending}</b> ta zayavka tasdiq kutmoqda!\n\n"
            "Hammasini bitta tugma bilan tasdiqlashingiz mumkin:",
            _confirm_kb(request.chat.id, pending),
        )


# ---------- Admin: ko'rish va tasdiqlash ----------

def _list_kb(rows: list[tuple[int, str, int]]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"✅ {title[:30]} — {count} ta", callback_data=f"jr:ask:{chat_id}")]
        for chat_id, title, count in rows if chat_id not in _running
    ]
    buttons.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="jr:list")])
    buttons.append([InlineKeyboardButton(text="⬅️ Admin panel", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _confirm_kb(chat_id: int, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Ha, {count} tasini tasdiqlash", callback_data=f"jr:go:{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="jr:list")],
    ])


async def _list_text() -> tuple[str, InlineKeyboardMarkup]:
    rows = await pending_by_chat()
    lines = ["📨 <b>Tasdiq kutayotgan zayavkalar</b>\n"]
    if not rows:
        lines.append("Hozircha kutayotgan zayavka yo'q.")
    for chat_id, title, count in rows:
        status = " — 🔄 <i>tasdiqlanmoqda...</i>" if chat_id in _running else ""
        lines.append(f"📣 <b>{h(title)}</b>: {count} ta{status}")
    lines.append(
        "\n<i>Bot zayavkalarni o'zi tasdiqlamaydi — ular yig'ilib turadi va faqat siz tasdiqlaysiz. "
        "Bot admin bo'lishidan oldin kelgan zayavkalar bu ro'yxatda yo'q.</i>"
    )
    return "\n".join(lines), _list_kb(rows)


@router.message(Command("zayavkalar", "requests"))
async def cmd_requests(message: Message) -> None:
    text, kb = await _list_text()
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "jr:list")
async def cb_list(callback: CallbackQuery) -> None:
    text, kb = await _list_text()
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass  # matn o'zgarmagan
    await callback.answer()


@router.callback_query(F.data.startswith("jr:ask:"))
async def cb_ask(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[2])
    count = await pending_count(chat_id)
    if not count:
        await callback.answer("Bu kanalda kutayotgan zayavka yo'q.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❓ <b>{count}</b> ta zayavkani tasdiqlaymizmi?\n\n"
        f"Taxminan {max(1, round(count * APPROVE_DELAY * 1.3 / 60))} daqiqa davom etadi. "
        "Jarayon fonda ketadi — bot bu vaqtda ham ishlayveradi.",
        reply_markup=_confirm_kb(chat_id, count),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("jr:go:"))
async def cb_go(callback: CallbackQuery) -> None:
    chat_id = int(callback.data.split(":")[2])
    if chat_id in _running:
        await callback.answer("Bu kanal zayavkalari allaqachon tasdiqlanmoqda.", show_alert=True)
        return
    count = await pending_count(chat_id)
    if not count:
        await callback.answer("Bu kanalda kutayotgan zayavka yo'q.", show_alert=True)
        return
    await callback.answer("Boshlandi")
    status = await callback.message.edit_text(f"🔄 Tasdiqlash boshlandi: 0 / {count}")
    _running.add(chat_id)
    task = asyncio.create_task(_approve_all(callback.bot, chat_id, count, status))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _approve_one(bot: Bot, chat_id: int, user_id: int) -> str:
    """"ok" | "gone" (so'rov endi yo'q) | "fatal" (bot huquqi yo'q — to'xtash kerak)."""
    for attempt in range(5):
        try:
            await bot.approve_chat_join_request(chat_id, user_id)
            return "ok"
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        except TelegramNetworkError:
            await asyncio.sleep(2 * (attempt + 1))
        except TelegramForbiddenError:
            return "fatal"  # bot kanaldan chiqarilgan
        except TelegramBadRequest as exc:
            msg = str(exc).upper()
            if "USER_ALREADY_PARTICIPANT" in msg:
                return "ok"
            if any(code in msg for code in _GONE_ERRORS):
                return "gone"
            if "CHAT_ADMIN_REQUIRED" in msg or "NOT ENOUGH RIGHTS" in msg or "CHAT NOT FOUND" in msg:
                return "fatal"
            logger.warning("Zayavka tasdiqlanmadi (chat=%s, user=%s): %s", chat_id, user_id, exc)
            return "gone"
    raise RuntimeError("Telegram bilan aloqa uzildi")


async def _mark(ok_ids: list[int], gone_ids: list[int]) -> None:
    async with get_session() as session:
        if ok_ids:
            await session.execute(update(JoinRequest).where(JoinRequest.id.in_(ok_ids)).values(approved=True))
        if gone_ids:
            await session.execute(update(JoinRequest).where(JoinRequest.id.in_(gone_ids)).values(failed=True))
        await session.commit()


async def _approve_all(bot: Bot, chat_id: int, total: int, status: Message) -> None:
    approved = gone = 0
    error = None
    try:
        while True:
            async with get_session() as session:
                batch = list((await session.execute(
                    select(JoinRequest.id, JoinRequest.user_id)
                    .where(JoinRequest.chat_id == chat_id, *_PENDING)
                    .order_by(JoinRequest.id)
                    .limit(BATCH_SIZE)
                )).all())
            if not batch:
                break
            ok_ids, gone_ids = [], []
            try:
                for row_id, user_id in batch:
                    result = await _approve_one(bot, chat_id, user_id)
                    if result == "fatal":
                        error = ("Botda bu kanalda zayavkalarni tasdiqlash huquqi yo'q. Botga "
                                 "«Foydalanuvchilarni qo'shish» huquqini bering va qayta urinib ko'ring.")
                        break
                    (ok_ids if result == "ok" else gone_ids).append(row_id)
                    await asyncio.sleep(APPROVE_DELAY)
            finally:
                # Jarayon uzilsa ham, shu paytgacha tasdiqlanganlar bazada belgilanib qolsin
                await _mark(ok_ids, gone_ids)
            done_before = approved + gone
            approved += len(ok_ids)
            gone += len(gone_ids)
            if error:
                break
            if (approved + gone) // PROGRESS_EVERY > done_before // PROGRESS_EVERY:
                try:
                    await status.edit_text(f"🔄 Tasdiqlanmoqda: {approved + gone} / {total}")
                except Exception:
                    pass
    except Exception:
        logger.exception("Zayavkalarni tasdiqlashda xatolik (chat=%s)", chat_id)
        error = "Kutilmagan xatolik (Telegram bilan aloqa uzilgan bo'lishi mumkin). Qolganlarini qayta tasdiqlang."
    finally:
        _running.discard(chat_id)

    remaining = await pending_count(chat_id)
    text = f"✅ Tasdiqlandi: <b>{approved}</b> ta"
    if gone:
        text += f"\n🚫 So'rovi bekor qilingan / allaqachon ko'rib chiqilgan: <b>{gone}</b> ta"
    if error:
        text = f"⚠️ {error}\n\n" + text + f"\n⏳ Hali kutmoqda: <b>{remaining}</b> ta"
    try:
        await status.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📨 Zayavkalar", callback_data="jr:list")]
        ]))
    except Exception:
        await _notify_admins(bot, text)
