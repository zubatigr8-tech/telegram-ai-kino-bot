"""Jonli joylashuv: har bir yangilanishda kameralarni tekshirib, ogohlantirish yuboradi
(avval ovozli, keyin matnli xabar)."""
import logging

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select

from antiradar.alerts import (
    RADAR_KINDS,
    SEARCH_RADIUS_M,
    Alert,
    CameraPoint,
    personal_overspeed,
    pick_alerts,
    tracker,
    thresholds_for,
    update_motion,
)
from antiradar.config import settings
from antiradar.db import Camera, User, cameras_near, get_session
from antiradar.handlers.subscription import pay_markup
from antiradar.i18n import LANGUAGES, t
from antiradar.keyboards import SPEED_OPTIONS, main_menu
from antiradar.voice import voice_sender

logger = logging.getLogger(__name__)
router = Router(name="location")


def alert_text(lang: str, alert: Alert, speed_kmh: float | None) -> str:
    cam = alert.camera
    # Masofani 10 metrgacha yaxlitlaymiz — aniq raqam haydovchiga kerak emas
    lines = [t(lang, "camera_alert", kind=t(lang, f"kind_{cam.kind}"), distance=int(round(alert.distance_m, -1)))]
    if cam.speed_limit:
        lines.append(t(lang, "speed_limit_line", limit=cam.speed_limit))
    if alert.overspeed and speed_kmh is not None:
        lines.append(t(lang, "overspeed_line", speed=round(speed_kmh)))
    return "\n".join(lines)


def alert_voice_text(lang: str, alert: Alert) -> str:
    # Masofa aniq metr emas, chegara (500 / 200) bilan aytiladi — shunda iboralar soni cheklangan
    # va har biri bir marta generatsiya qilinib keshlanadi
    cam = alert.camera
    parts = [t(lang, "voice_camera", kind=t(lang, f"kind_{cam.kind}"), distance=alert.threshold_m)]
    if cam.speed_limit:
        parts.append(t(lang, "voice_limit", limit=cam.speed_limit))
    if alert.overspeed:
        parts.append(t(lang, "voice_overspeed"))
    return " ".join(parts)


async def warm_voice_cache() -> None:
    """Bazadagi kamera turlari/limitlari uchun barcha ovozli iboralarni oldindan tayyorlaydi,
    shunda yo'lda ogohlantirish TTS'ni kutmasdan darhol yuboriladi."""
    if not settings.VOICE_ENABLED:
        return
    async with get_session() as session:
        combos = (await session.execute(
            select(Camera.kind, Camera.speed_limit).where(Camera.is_active.is_(True)).distinct()
        )).all()
    phrases = []
    for lang in LANGUAGES:
        for kind, limit in combos:
            cam = CameraPoint(id=0, lat=0, lon=0, kind=kind, speed_limit=limit)
            for threshold in thresholds_for(kind):
                for overspeed in (False, True):
                    alert = Alert(camera=cam, distance_m=threshold, threshold_m=threshold, overspeed=overspeed)
                    phrases.append((lang, alert_voice_text(lang, alert)))
        phrases += [(lang, t(lang, "voice_personal_overspeed", limit=s)) for s in SPEED_OPTIONS]
    ready = await voice_sender.warmup(list(dict.fromkeys(phrases)))
    logger.info("Ovozli iboralar tayyor: %s / %s", ready, len(set(phrases)))


async def notify(bot: Bot, chat_id: int, lang: str, voice_text: str, text: str) -> None:
    """Avval ovozli xabar (haydovchi ekranga qaramasdan eshitadi), keyin matnli."""
    if settings.VOICE_ENABLED:
        await voice_sender.send(bot, chat_id, lang, voice_text)
    await bot.send_message(chat_id, text)


async def process_point(bot: Bot, message: Message, user: User) -> None:
    lang = user.lang
    state = tracker.get(user.tg_id)

    if not user.has_access():
        if not state.expired_notified:
            state.expired_notified = True
            await bot.send_message(user.tg_id, t(lang, "sub_expired"), reply_markup=await pay_markup(bot, lang))
        return

    loc = message.location
    # edit_date — unix vaqt (int), date — datetime
    ts = float(message.edit_date) if message.edit_date else message.date.timestamp()
    update_motion(state, loc.latitude, loc.longitude, ts, loc.heading)

    cameras = [
        CameraPoint(
            id=c.id, lat=c.lat, lon=c.lon, kind=c.kind, speed_limit=c.speed_limit, direction=c.direction
        )
        for c in await cameras_near(loc.latitude, loc.longitude, SEARCH_RADIUS_M)
        if user.signs_enabled or c.kind in RADAR_KINDS
    ]
    for alert in pick_alerts(state, cameras):
        await notify(bot, user.tg_id, lang, alert_voice_text(lang, alert), alert_text(lang, alert, state.speed_kmh))

    if personal_overspeed(state, user.max_speed):
        await notify(
            bot,
            user.tg_id,
            lang,
            t(lang, "voice_personal_overspeed", limit=user.max_speed),
            t(lang, "personal_overspeed", speed=round(state.speed_kmh), limit=user.max_speed),
        )


@router.message(F.location.live_period)
async def live_location_started(message: Message, bot: Bot, db_user: User) -> None:
    tracker.reset(db_user.tg_id)
    if db_user.has_access():
        await message.answer(t(db_user.lang, "live_started"), reply_markup=main_menu(db_user.lang))
    await process_point(bot, message, db_user)


@router.edited_message(F.location)
async def live_location_updated(message: Message, bot: Bot, db_user: User) -> None:
    await process_point(bot, message, db_user)


@router.message(F.location)
async def static_location(message: Message, db_user: User) -> None:
    await message.answer(t(db_user.lang, "static_location_hint") + "\n\n" + t(db_user.lang, "how_to"))


@router.message()
async def fallback(message: Message, db_user: User) -> None:
    await message.answer(t(db_user.lang, "unknown"), reply_markup=main_menu(db_user.lang))
