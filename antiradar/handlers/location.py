"""Jonli joylashuv: har bir yangilanishda kameralarni tekshirib, ogohlantirish yuboradi."""
from aiogram import Bot, F, Router
from aiogram.types import Message

from antiradar.alerts import (
    SEARCH_RADIUS_M,
    Alert,
    CameraPoint,
    personal_overspeed,
    pick_alerts,
    tracker,
    update_motion,
)
from antiradar.db import User, cameras_near
from antiradar.handlers.subscription import pay_markup
from antiradar.i18n import t
from antiradar.keyboards import main_menu

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
    ]
    for alert in pick_alerts(state, cameras):
        await bot.send_message(user.tg_id, alert_text(lang, alert, state.speed_kmh))

    if personal_overspeed(state, user.max_speed):
        await bot.send_message(
            user.tg_id, t(lang, "personal_overspeed", speed=round(state.speed_kmh), limit=user.max_speed)
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
