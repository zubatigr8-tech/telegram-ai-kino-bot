"""Ogohlantirish mantiqi (Telegram'ga bog'liq emas, alohida test qilinadi).

Har bir jonli joylashuv yangilanishida:
1. oldingi nuqtadan tezlik va yo'nalish hisoblanadi;
2. atrofdagi kameralardan faqat OLDINDA va haydovchi yo'nalishiga mos kelganlari tanlanadi;
3. har kamera uchun har masofa chegarasida (500 m, 200 m) faqat bir marta ogohlantiriladi.
"""
import time
from dataclasses import dataclass, field

from antiradar.geo import angle_diff, bearing_deg, distance_m

ALERT_THRESHOLDS_M = (500, 200)  # kattadan kichikka
SEARCH_RADIUS_M = 1200
RESET_DISTANCE_M = 1000  # kameradan shuncha uzoqlashgach, keyingi safar yana ogohlantiriladi
AHEAD_MAX_ANGLE = 50  # kamera haydovchi yo'nalishidan shu burchak ichida bo'lsa — "oldinda"
CAMERA_DIRECTION_MAX_ANGLE = 60
MIN_MOVE_FOR_HEADING_M = 15
MIN_SPEED_INTERVAL_S = 2
MAX_REAL_SPEED_KMH = 250  # GPS sakrashlarini e'tiborsiz qoldirish uchun
OVERSPEED_TOLERANCE_KMH = 5
PERSONAL_OVERSPEED_COOLDOWN_S = 60
TRACK_TTL_S = 3600


@dataclass
class CameraPoint:
    id: int
    lat: float
    lon: float
    kind: str = "fixed"
    speed_limit: int | None = None
    direction: float | None = None


@dataclass
class Alert:
    camera: CameraPoint
    distance_m: float
    threshold_m: int  # qaysi chegarada (500 / 200 m) — ovozli ibora shu raqam bilan aytiladi
    overspeed: bool  # haydovchi shu kamera limitidan oshib ketyapti


@dataclass
class TrackState:
    lat: float | None = None
    lon: float | None = None
    ts: float = 0.0
    speed_kmh: float | None = None
    heading: float | None = None
    # kamera id -> ogohlantirilgan eng kichik chegara (m)
    alerted: dict[int, int] = field(default_factory=dict)
    last_personal_overspeed_ts: float = 0.0
    expired_notified: bool = False


def update_motion(state: TrackState, lat: float, lon: float, ts: float, heading: float | None) -> None:
    """Yangi nuqta bo'yicha tezlik va yo'nalishni yangilaydi."""
    if state.lat is not None and state.lon is not None:
        moved = distance_m(state.lat, state.lon, lat, lon)
        dt = ts - state.ts
        if dt >= MIN_SPEED_INTERVAL_S:
            speed = moved / dt * 3.6
            if speed <= MAX_REAL_SPEED_KMH:
                state.speed_kmh = speed
        if heading is None and moved >= MIN_MOVE_FOR_HEADING_M:
            heading = bearing_deg(state.lat, state.lon, lat, lon)
    if heading is not None:
        state.heading = heading
    state.lat, state.lon, state.ts = lat, lon, ts


def _is_relevant(cam: CameraPoint, lat: float, lon: float, heading: float | None) -> bool:
    if heading is None:
        return True  # yo'nalish noma'lum — xavfsizlik uchun hammasidan ogohlantiramiz
    if angle_diff(heading, bearing_deg(lat, lon, cam.lat, cam.lon)) > AHEAD_MAX_ANGLE:
        return False  # kamera orqada yoki yon tomonda
    if cam.direction is not None and angle_diff(heading, cam.direction) > CAMERA_DIRECTION_MAX_ANGLE:
        return False  # qarama-qarshi yo'lakni o'lchaydi
    return True


def pick_alerts(state: TrackState, cameras: list[CameraPoint]) -> list[Alert]:
    """update_motion'dan keyin chaqiriladi. Yangi ogohlantirishlar ro'yxatini qaytaradi."""
    if state.lat is None or state.lon is None:
        return []
    lat, lon = state.lat, state.lon

    distances = {cam.id: distance_m(lat, lon, cam.lat, cam.lon) for cam in cameras}
    # Uzoqlashgan (yoki qidiruvga tushmagan) kameralar uchun ogohlantirish hisobini tozalaymiz
    for cam_id in list(state.alerted):
        if distances.get(cam_id, RESET_DISTANCE_M + 1) > RESET_DISTANCE_M:
            del state.alerted[cam_id]

    alerts = []
    for cam in sorted(cameras, key=lambda c: distances[c.id]):
        dist = distances[cam.id]
        crossed = [t for t in ALERT_THRESHOLDS_M if dist <= t]
        if not crossed:
            continue
        threshold = min(crossed)
        if state.alerted.get(cam.id, 10**9) <= threshold:
            continue  # bu chegarada allaqachon ogohlantirilgan
        if not _is_relevant(cam, lat, lon, state.heading):
            continue
        state.alerted[cam.id] = threshold
        overspeed = (
            cam.speed_limit is not None
            and state.speed_kmh is not None
            and state.speed_kmh > cam.speed_limit + OVERSPEED_TOLERANCE_KMH
        )
        alerts.append(Alert(camera=cam, distance_m=dist, threshold_m=threshold, overspeed=overspeed))
    return alerts


def personal_overspeed(state: TrackState, max_speed: int | None, now: float | None = None) -> bool:
    """Shaxsiy tezlik chegarasidan oshilganmi (daqiqasiga ko'pi bilan bir marta)."""
    if not max_speed or state.speed_kmh is None or state.speed_kmh <= max_speed:
        return False
    now = time.time() if now is None else now
    if now - state.last_personal_overspeed_ts < PERSONAL_OVERSPEED_COOLDOWN_S:
        return False
    state.last_personal_overspeed_ts = now
    return True


class Tracker:
    """Foydalanuvchilarning harakat holati (xotirada). Eski yozuvlar vaqti-vaqti bilan tozalanadi."""

    def __init__(self) -> None:
        self._states: dict[int, TrackState] = {}
        self._last_cleanup = 0.0

    def get(self, user_id: int) -> TrackState:
        now = time.time()
        if now - self._last_cleanup > 300:
            self._states = {uid: s for uid, s in self._states.items() if now - s.ts < TRACK_TTL_S}
            self._last_cleanup = now
        return self._states.setdefault(user_id, TrackState())

    def reset(self, user_id: int) -> TrackState:
        self._states[user_id] = TrackState()
        return self._states[user_id]


tracker = Tracker()
