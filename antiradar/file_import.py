"""Tayyor ro'yxatdan (CSV) radar va yo'l belgilarini import qilish.

Admin botga .csv fayl yuboradi. Ustunlar (sarlavha qatori majburiy, tartib ahamiyatsiz):
    lat, lon            — koordinatalar (majburiy)
    kind                — turi (ixtiyoriy, standart: fixed). RADAR_KINDS yoki SIGN_KINDS dan biri
    speed_limit         — tezlik chegarasi, km/soat (ixtiyoriy)
    direction           — kamera o'lchaydigan yo'nalish, 0-360° (ixtiyoriy)
Ajratuvchi vergul yoki nuqtali vergul bo'lishi mumkin (Excel'dan saqlangan fayllar uchun).
Bir xil turdagi nuqta 15 m ichida allaqachon bo'lsa, takror qo'shilmaydi.
"""
import csv
import io
from dataclasses import dataclass

from sqlalchemy import select

from antiradar.alerts import RADAR_KINDS, SIGN_KINDS
from antiradar.config import settings
from antiradar.db import Camera, get_session
from antiradar.geo import distance_m

DUPLICATE_RADIUS_M = 15
ALL_KINDS = set(RADAR_KINDS) | set(SIGN_KINDS)
# Ruscha/o'zbekcha sarlavhali fayllar uchun ham
HEADER_ALIASES = {
    "lat": "lat", "latitude": "lat", "широта": "lat", "kenglik": "lat",
    "lon": "lon", "lng": "lon", "longitude": "lon", "долгота": "lon", "uzunlik": "lon",
    "kind": "kind", "type": "kind", "тип": "kind", "turi": "kind",
    "speed_limit": "speed_limit", "limit": "speed_limit", "maxspeed": "speed_limit",
    "ограничение": "speed_limit", "tezlik": "speed_limit",
    "direction": "direction", "направление": "direction", "yonalish": "direction",
}


@dataclass
class ParsedPoint:
    lat: float
    lon: float
    kind: str
    speed_limit: int | None
    direction: float | None


def _num(raw: str | None) -> float | None:
    raw = (raw or "").strip().replace(",", ".")
    return float(raw) if raw else None


def parse_csv(text: str) -> tuple[list[ParsedPoint], list[str]]:
    """(nuqtalar, xatolar) qaytaradi. Xato qatorlar o'tkazib yuboriladi."""
    text = text.lstrip("﻿")
    first_line = text.splitlines()[0] if text else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = {name: HEADER_ALIASES.get((name or "").strip().lower()) for name in reader.fieldnames or []}
    if "lat" not in columns.values() or "lon" not in columns.values():
        return [], ["Faylda lat va lon ustunlari topilmadi"]

    points, errors = [], []
    for line_no, raw_row in enumerate(reader, start=2):
        row = {columns[k]: v for k, v in raw_row.items() if columns.get(k)}
        try:
            lat, lon = _num(row.get("lat")), _num(row.get("lon"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("koordinata noto'g'ri")
            kind = (row.get("kind") or "fixed").strip().lower()
            if kind not in ALL_KINDS:
                raise ValueError(f"noma'lum tur: {kind}")
            limit = _num(row.get("speed_limit"))
            direction = _num(row.get("direction"))
            points.append(
                ParsedPoint(
                    lat=lat,
                    lon=lon,
                    kind=kind,
                    speed_limit=int(limit) if limit else None,
                    direction=direction % 360 if direction is not None else None,
                )
            )
        except ValueError as exc:
            errors.append(f"{line_no}-qator: {exc}")
    return points, errors


async def save_points(points: list[ParsedPoint]) -> tuple[int, int]:
    """(qo'shildi, takror sababli o'tkazib yuborildi) qaytaradi."""
    added = skipped = 0
    async with get_session() as session:
        existing = [
            (c.lat, c.lon, c.kind)
            for c in await session.scalars(select(Camera).where(Camera.is_active.is_(True)))
        ]
        for p in points:
            if any(
                kind == p.kind and abs(lat - p.lat) < 0.001 and distance_m(lat, lon, p.lat, p.lon) <= DUPLICATE_RADIUS_M
                for lat, lon, kind in existing
            ):
                skipped += 1
                continue
            session.add(
                Camera(
                    country=settings.COUNTRY,
                    lat=p.lat,
                    lon=p.lon,
                    kind=p.kind,
                    speed_limit=p.speed_limit,
                    direction=p.direction,
                    source="file",
                )
            )
            existing.append((p.lat, p.lon, p.kind))
            added += 1
        await session.commit()
    return added, skipped
