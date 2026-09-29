"""Admin buyruqlari (faqat ANTIRADAR_ADMIN_IDS uchun):
- /stats — statistika;
- oddiy (jonli emas) joylashuv yuborish → shu nuqtaga kamera yoki yo'l belgisi qo'shish;
- /delcam <id> — kamerani o'chirish;
- .csv fayl yuborish — tayyor ro'yxatdan radar/belgilarni yuklash (antiradar/file_import.py);
- /osm — OpenStreetMap'dan hozir yangilash (bot buni har kuni o'zi ham qiladi)."""
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, or_, select

from antiradar.alerts import RADAR_KINDS, SIGN_KINDS
from antiradar.config import settings
from antiradar.db import Camera, Payment, User, get_session, utcnow
from antiradar.file_import import parse_csv, save_points
from antiradar.osm_import import import_country

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(settings.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(settings.ADMIN_IDS))

KINDS = {
    "fixed": "📷 Kamera",
    "mobile": "📡 Mobil radar",
    "red_light": "🚦 Svetofor",
    "average": "📏 O'rtacha tezlik",
    "police": "👮 YPX posti",
    # Yo'l belgilari
    "speed_limit": "🔢 Tezlik cheklovi",
    "crossing": "🚸 Piyodalar o'tish joyi",
    "stop": "🛑 STOP",
    "give_way": "🔻 Yo'l bering",
    "speed_bump": "〰️ Sun'iy notekislik",
    "railway_crossing": "🚂 Temir yo'l kesishmasi",
    "children": "🧒 Bolalar",
}
# Faqat shu turlarda tezlik chegarasi so'raladi, qolganlari darhol qo'shiladi
KINDS_WITH_LIMIT = {"fixed", "mobile", "red_light", "average", "police", "speed_limit"}
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
        cameras = await session.scalar(
            select(func.count()).select_from(Camera).where(Camera.is_active.is_(True), Camera.kind.in_(RADAR_KINDS))
        )
        signs = await session.scalar(
            select(func.count()).select_from(Camera).where(Camera.is_active.is_(True), Camera.kind.in_(SIGN_KINDS))
        )
        stars = await session.scalar(select(func.coalesce(func.sum(Payment.amount), 0)))
    await message.answer(
        "📊 <b>Statistika</b>\n\n"
        f"👤 Foydalanuvchilar: {users}\n"
        f"✅ Faol (sinov + obuna): {active}\n"
        f"⭐ Pullik obunachilar: {paid}\n"
        f"📷 Kameralar/radarlar: {cameras}\n"
        f"🪧 Yo'l belgilari: {signs}\n"
        f"💰 Jami tushum: {stars} Stars"
    )


@router.message(F.location & ~F.location.live_period)
async def admin_location(message: Message) -> None:
    lat, lon = message.location.latitude, message.location.longitude
    buttons = [InlineKeyboardButton(text=label, callback_data=f"ak:{lat:.6f}:{lon:.6f}:{kind}")
               for kind, label in KINDS.items()]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    await message.answer(
        f"➕ Shu nuqtaga ({lat:.5f}, {lon:.5f}) kamera yoki yo'l belgisi qo'shilsinmi? Turini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("ak:"))
async def admin_pick_kind(callback: CallbackQuery) -> None:
    _, lat, lon, kind = callback.data.split(":")
    if kind not in KINDS_WITH_LIMIT:
        await add_camera(callback, lat, lon, kind, 0)
        return
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
    await add_camera(callback, lat, lon, kind, int(limit))


async def add_camera(callback: CallbackQuery, lat: str, lon: str, kind: str, limit: int) -> None:
    if kind not in KINDS:
        await callback.answer()
        return
    async with get_session() as session:
        camera = Camera(lat=float(lat), lon=float(lon), kind=kind, speed_limit=limit or None, source="admin")
        session.add(camera)
        await session.commit()
    await callback.answer("✅")
    await callback.message.edit_text(
        f"✅ Qo'shildi (ID: <code>{camera.id}</code>): {KINDS[kind]}, "
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


MAX_CSV_BYTES = 5 * 1024 * 1024


@router.message(F.document.file_name.lower().endswith(".csv"))
async def import_csv(message: Message, bot: Bot) -> None:
    if message.document.file_size and message.document.file_size > MAX_CSV_BYTES:
        await message.answer("Fayl juda katta (5 MB dan oshmasin).")
        return
    buffer = await bot.download(message.document)
    raw = buffer.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")  # Excel'ning ruscha Windows kodirovkasi
    points, errors = parse_csv(text)
    added, skipped = await save_points(points)
    report = f"📥 Import: ✅ {added} ta qo'shildi, ↩️ {skipped} ta takror, ❌ {len(errors)} ta xato."
    if errors:
        report += "\n\n" + "\n".join(errors[:10])
    await message.answer(report)


@router.message(Command("osm"))
async def cmd_osm(message: Message) -> None:
    await message.answer("⏳ OpenStreetMap'dan yangilanmoqda...")
    try:
        added, updated, removed = await import_country(settings.COUNTRY)
    except Exception as exc:
        await message.answer(f"❌ Xatolik: {exc}")
        return
    await message.answer(f"✅ OSM: +{added} yangi, {updated} yangilandi, -{removed} o'chirildi.")
