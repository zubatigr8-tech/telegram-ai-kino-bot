"""Admin buyruqlari (faqat ANTIRADAR_ADMIN_IDS uchun):
- /stats — statistika;
- oddiy (jonli emas) joylashuv yuborish → shu nuqtaga kamera qo'shish;
- /delcam <id> — kamerani o'chirish."""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, or_, select

from antiradar.config import settings
from antiradar.db import Camera, Payment, User, get_session, utcnow

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(settings.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(settings.ADMIN_IDS))

KINDS = {
    "fixed": "📷 Kamera",
    "mobile": "📡 Mobil radar",
    "red_light": "🚦 Svetofor",
    "average": "📏 O'rtacha tezlik",
    "police": "👮 YPX posti",
}
LIMITS = (40, 50, 60, 70, 80, 90, 100, 0)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    now = utcnow()
    async with get_session() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        active = await session.scalar(
            select(func.count()).select_from(User).where(or_(User.trial_until > now, User.paid_until > now))
        )
        paid = await session.scalar(select(func.count()).select_from(User).where(User.paid_until > now))
        cameras = await session.scalar(select(func.count()).select_from(Camera).where(Camera.is_active.is_(True)))
        stars = await session.scalar(select(func.coalesce(func.sum(Payment.amount), 0)))
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"✅ Faol (sinov + obuna): {active}\n"
        f"⭐ Pullik obunachilar: {paid}\n"
        f"📷 Kameralar: {cameras}\n"
        f"💰 Jami tushum: {stars} Stars"
    )


@router.message(F.location & ~F.location.live_period)
async def admin_location(message: Message) -> None:
    lat, lon = message.location.latitude, message.location.longitude
    rows = [[InlineKeyboardButton(text=label, callback_data=f"ak:{lat:.6f}:{lon:.6f}:{kind}")]
            for kind, label in KINDS.items()]
    await message.answer(
        f"➕ Shu nuqtaga ({lat:.5f}, {lon:.5f}) kamera qo'shilsinmi? Turini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("ak:"))
async def admin_pick_kind(callback: CallbackQuery) -> None:
    _, lat, lon, kind = callback.data.split(":")
    buttons = [
        InlineKeyboardButton(text=str(limit) if limit else "Limitsiz", callback_data=f"al:{lat}:{lon}:{kind}:{limit}")
        for limit in LIMITS
    ]
    await callback.answer()
    await callback.message.edit_text(
        f"{KINDS.get(kind, kind)} — tezlik chegarasini tanlang (km/soat):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons[:4], buttons[4:]]),
    )


@router.callback_query(F.data.startswith("al:"))
async def admin_add_camera(callback: CallbackQuery) -> None:
    _, lat, lon, kind, limit = callback.data.split(":")
    if kind not in KINDS:
        await callback.answer()
        return
    async with get_session() as session:
        camera = Camera(lat=float(lat), lon=float(lon), kind=kind, speed_limit=int(limit) or None, source="admin")
        session.add(camera)
        await session.commit()
    await callback.answer("✅")
    await callback.message.edit_text(
        f"✅ Kamera qo'shildi (ID: <code>{camera.id}</code>): {KINDS[kind]}, "
        f"limit: {camera.speed_limit or '—'}\nO'chirish: /delcam {camera.id}"
    )


@router.message(Command("delcam"))
async def cmd_delcam(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Foydalanish: /delcam <id>")
        return
    async with get_session() as session:
        camera = await session.get(Camera, int(arg))
        if camera is None:
            await message.answer("Bunday kamera topilmadi.")
            return
        camera.is_active = False
        await session.commit()
    await message.answer(f"🗑 Kamera {arg} o'chirildi.")
