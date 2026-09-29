"""OpenStreetMap'dan tezlik kameralari va yo'l belgilarini bazaga import qilish.

Ishlatish:  python -m antiradar.osm_import          (standart: O'zbekiston)
            python -m antiradar.osm_import KZ       (boshqa davlat, ISO kodi)
Qayta ishga tushirilsa, mavjud kameralar yangilanadi (osm_id bo'yicha), takror qo'shilmaydi.
Bot ishlayotganda buni o'zi har OSM_REFRESH_HOURS soatda bajaradi (run_osm_worker).
"""
import asyncio
import json
import logging
import re
import sys
import urllib.parse
import urllib.request

from sqlalchemy import select

from antiradar.config import settings
from antiradar.db import Camera, get_session, init_db

logger = logging.getLogger(__name__)

MPH_TO_KMH = 1.609344
CARDINALS = {
    "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
    "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5, "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
}


def build_query(country: str) -> str:
    return (
        "[out:json][timeout:300];"
        f'area["ISO3166-1"="{country}"][admin_level=2]->.a;'
        '(node["highway"="speed_camera"](area.a);'
        'node["enforcement"="maxspeed"](area.a);'
        # Yo'l belgilari
        'node["highway"~"^(crossing|stop|give_way)$"](area.a);'
        'node["traffic_calming"](area.a);'
        'node["railway"="level_crossing"](area.a);'
        'node["hazard"="children"](area.a);'
        'node["traffic_sign"]["maxspeed"](area.a););'
        "out body;"
    )


def parse_maxspeed(raw: str | None) -> int | None:
    if not raw:
        return None
    match = re.match(r"\s*(\d+)\s*(mph)?", raw)
    if not match:
        return None
    value = int(match.group(1))
    if match.group(2):
        value = round(value * MPH_TO_KMH)
    return value if 5 <= value <= 200 else None


def parse_direction(raw: str | None) -> float | None:
    if not raw:
        return None
    raw = raw.strip().upper()
    if raw in CARDINALS:
        return float(CARDINALS[raw])
    try:
        return float(raw) % 360
    except ValueError:
        return None  # "forward", "both" va h.k. — yo'nalish noma'lum deb olamiz


SPEED_BUMPS = {"bump", "hump", "table", "cushion", "yes", "mini_bumps", "dip"}


def parse_kind(tags: dict) -> str | None:
    """OSM teglaridan tur; None — kerak emas (masalan crossing=no)."""
    if tags.get("highway") == "speed_camera" or tags.get("enforcement"):
        if tags.get("enforcement") == "traffic_signals" or tags.get("camera:type") == "red_light":
            return "red_light"
        if tags.get("enforcement") == "average_speed":
            return "average"
        return "fixed"
    if tags.get("railway") == "level_crossing":
        return "railway_crossing"
    if tags.get("hazard") == "children":
        return "children"
    highway = tags.get("highway")
    if highway == "crossing" and tags.get("crossing") != "no":
        return "crossing"
    if highway in ("stop", "give_way"):
        return highway
    if tags.get("traffic_calming") in SPEED_BUMPS:
        return "speed_bump"
    if tags.get("traffic_sign") and parse_maxspeed(tags.get("maxspeed")):
        return "speed_limit"
    return None


def fetch(country: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": build_query(country)}).encode()
    request = urllib.request.Request(
        settings.OVERPASS_URL, data=data, headers={"User-Agent": "antiradar-telegram-bot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=330) as response:
        return json.loads(response.read())["elements"]


async def import_country(country: str) -> tuple[int, int, int]:
    """(qo'shildi, yangilandi, o'chirildi) qaytaradi."""
    await init_db()
    elements = await asyncio.to_thread(fetch, country)
    added = updated = removed = 0
    seen: set[int] = set()
    async with get_session() as session:
        existing = {
            c.osm_id: c
            for c in await session.scalars(
                select(Camera).where(Camera.osm_id.is_not(None), Camera.country == country)
            )
        }
        for el in elements:
            if el.get("type") != "node":
                continue
            tags = el.get("tags", {})
            kind = parse_kind(tags)
            if kind is None:
                continue
            seen.add(el["id"])
            fields = dict(
                country=country,
                lat=el["lat"],
                lon=el["lon"],
                kind=kind,
                speed_limit=parse_maxspeed(tags.get("maxspeed")),
                direction=parse_direction(tags.get("direction") or tags.get("camera:direction")),
                is_active=True,
            )
            camera = existing.get(el["id"])
            if camera is None:
                camera = Camera(osm_id=el["id"], source="osm", **fields)
                session.add(camera)
                existing[el["id"]] = camera
                added += 1
            else:
                for key, value in fields.items():
                    setattr(camera, key, value)
                updated += 1
        # OSM'dan olib tashlangan nuqtalarni o'chiramiz. Javob bo'sh bo'lsa (server nosozligi
        # bo'lishi mumkin) — hech narsani o'chirmaymiz.
        if seen:
            for osm_id, camera in existing.items():
                if osm_id not in seen and camera.is_active:
                    camera.is_active = False
                    removed += 1
        await session.commit()
    return added, updated, removed


async def run_osm_worker(on_updated=None) -> None:
    """Bot ichida fon vazifasi: ishga tushganda va har OSM_REFRESH_HOURS soatda OSM'dan yangilaydi."""
    if settings.OSM_REFRESH_HOURS <= 0:
        return
    while True:
        try:
            added, updated, removed = await import_country(settings.COUNTRY)
            logger.info("OSM yangilandi: +%s, ~%s, -%s", added, updated, removed)
            if on_updated is not None:
                await on_updated()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("OSM'dan yangilab bo'lmadi: %s", exc)
        await asyncio.sleep(settings.OSM_REFRESH_HOURS * 3600)


def main() -> None:
    country = (sys.argv[1] if len(sys.argv) > 1 else settings.COUNTRY).upper()
    added, updated, removed = asyncio.run(import_country(country))
    print(f"{country}: {added} ta yangi nuqta (kamera/belgi) qo'shildi, {updated} ta yangilandi, {removed} ta o'chirildi.")


if __name__ == "__main__":
    main()
