"""OpenStreetMap'dan tezlik kameralarini bazaga import qilish.

Ishlatish:  python -m antiradar.osm_import          (standart: O'zbekiston)
            python -m antiradar.osm_import KZ       (boshqa davlat, ISO kodi)
Qayta ishga tushirilsa, mavjud kameralar yangilanadi (osm_id bo'yicha), takror qo'shilmaydi.
"""
import asyncio
import json
import re
import sys
import urllib.parse
import urllib.request

from sqlalchemy import select

from antiradar.config import settings
from antiradar.db import Camera, get_session, init_db

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
        'node["enforcement"="maxspeed"](area.a););'
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


def parse_kind(tags: dict) -> str:
    if tags.get("enforcement") == "traffic_signals" or tags.get("camera:type") == "red_light":
        return "red_light"
    if tags.get("enforcement") == "average_speed":
        return "average"
    return "fixed"


def fetch(country: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": build_query(country)}).encode()
    request = urllib.request.Request(
        settings.OVERPASS_URL, data=data, headers={"User-Agent": "antiradar-telegram-bot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=330) as response:
        return json.loads(response.read())["elements"]


async def import_country(country: str) -> tuple[int, int]:
    await init_db()
    elements = await asyncio.to_thread(fetch, country)
    added = updated = 0
    async with get_session() as session:
        existing = {
            c.osm_id: c
            for c in await session.scalars(select(Camera).where(Camera.osm_id.is_not(None)))
        }
        for el in elements:
            if el.get("type") != "node":
                continue
            tags = el.get("tags", {})
            fields = dict(
                country=country,
                lat=el["lat"],
                lon=el["lon"],
                kind=parse_kind(tags),
                speed_limit=parse_maxspeed(tags.get("maxspeed")),
                direction=parse_direction(tags.get("direction") or tags.get("camera:direction")),
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
        await session.commit()
    return added, updated


def main() -> None:
    country = (sys.argv[1] if len(sys.argv) > 1 else settings.COUNTRY).upper()
    added, updated = asyncio.run(import_country(country))
    print(f"{country}: {added} ta yangi kamera qo'shildi, {updated} ta yangilandi.")


if __name__ == "__main__":
    main()
