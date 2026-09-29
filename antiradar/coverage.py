"""OpenStreetMap radarlar bazasi qanchalik to'liq ekanini o'lchash.

Ishlatish:
    python -m antiradar.coverage                         # OSM'da O'zbekiston bo'yicha nechta radar/kamera bor
    python -m antiradar.coverage rasmiy_royxat.xlsx      # + rasmiy ro'yxat bilan solishtirib, foizni chiqaradi
    python -m antiradar.coverage royxat.csv --radius 150 # mos kelish masofasi (standart 100 m)

Rasmiy ro'yxatdagi har bir nuqta uchun OSM'dagi eng yaqin radar/kamera topiladi. U `radius`
metr ichida bo'lsa — "OSM biladi" deb hisoblanadi. Natija: foiz va topilmagan nuqtalar.
"""
import argparse
import asyncio
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from antiradar.config import settings
from antiradar.file_import import ParsedPoint, parse_file
from antiradar.geo import distance_m
from antiradar.osm_import import parse_kind

TARGET_PERCENT = 80
OFFICIAL_TOTAL_ESTIMATE = 2500  # Rasmiy ma'lumotlarga ko'ra O'zbekistonda 2 500 dan ortiq kamera va radar


def radar_query(country: str) -> str:
    # Nuqta (node) sifatida belgilangan kameralar va "enforcement" relation'laridagi qurilmalar
    return (
        "[out:json][timeout:300];"
        f'area["ISO3166-1"="{country}"][admin_level=2]->.a;'
        '(node["highway"="speed_camera"](area.a);'
        'node["enforcement"](area.a);'
        'node["man_made"="surveillance"]["surveillance:type"="camera"]["surveillance"~"traffic"](area.a););'
        "out body;"
        'relation["type"="enforcement"](area.a);'
        "node(r:\"device\");"
        "out body;"
    )


def fetch_osm_radars(country: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": radar_query(country)}).encode()
    request = urllib.request.Request(
        settings.OVERPASS_URL, data=data, headers={"User-Agent": "antiradar-telegram-bot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=330) as response:
        elements = json.loads(response.read())["elements"]
    unique = {el["id"]: el for el in elements if el.get("type") == "node"}
    return list(unique.values())


@dataclass
class CoverageResult:
    total: int
    matched: int
    unmatched: list[tuple[ParsedPoint, float]]  # (nuqta, eng yaqin OSM gacha masofa)

    @property
    def percent(self) -> float:
        return 100 * self.matched / self.total if self.total else 0.0


def compare(reference: list[ParsedPoint], osm: list[tuple[float, float]], radius_m: float) -> CoverageResult:
    matched, unmatched = 0, []
    for point in reference:
        nearest = min(
            (distance_m(point.lat, point.lon, lat, lon) for lat, lon in osm if abs(lat - point.lat) < 0.05),
            default=float("inf"),
        )
        if nearest <= radius_m:
            matched += 1
        else:
            unmatched.append((point, nearest))
    return CoverageResult(total=len(reference), matched=matched, unmatched=unmatched)


def main() -> None:
    parser = argparse.ArgumentParser(description="OSM radarlar bazasi to'liqligini o'lchash")
    parser.add_argument("reference", nargs="?", help="Rasmiy ro'yxat (.xlsx yoki .csv)")
    parser.add_argument("--radius", type=float, default=100, help="Mos kelish masofasi, metr")
    args = parser.parse_args()

    print(f"⏳ OpenStreetMap'dan {settings.COUNTRY} radarlari yuklanmoqda...")
    elements = asyncio.run(asyncio.to_thread(fetch_osm_radars, settings.COUNTRY))
    by_kind: dict[str, int] = {}
    for el in elements:
        kind = parse_kind(el.get("tags", {})) or "fixed"
        by_kind[kind] = by_kind.get(kind, 0) + 1
    print(f"\n📡 OSM'da jami radar/kamera: {len(elements)}")
    for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
        print(f"   {kind}: {count}")
    print(
        f"   Rasmiy taxminiy son ~{OFFICIAL_TOTAL_ESTIMATE} → OSM qamrovi taxminan "
        f"{100 * len(elements) / OFFICIAL_TOTAL_ESTIMATE:.0f}%"
    )

    if not args.reference:
        return
    path = Path(args.reference)
    reference, errors = parse_file(path.name, path.read_bytes())
    if errors:
        print(f"\n⚠️ Ro'yxatda {len(errors)} ta xato qator o'tkazib yuborildi")
    result = compare(reference, [(el["lat"], el["lon"]) for el in elements], args.radius)
    verdict = "✅ YETARLI" if result.percent >= TARGET_PERCENT else "❌ YETARLI EMAS"
    print(
        f"\n📊 Rasmiy ro'yxat bilan solishtirish ({args.radius:.0f} m ichida):\n"
        f"   {result.matched} / {result.total} ta nuqtani OSM biladi — {result.percent:.0f}%  "
        f"(maqsad {TARGET_PERCENT}%) {verdict}"
    )
    if result.unmatched:
        print("\n   OSM'da topilmaganlar (dastlabki 20 tasi):")
        for point, dist in result.unmatched[:20]:
            near = f"eng yaqini {dist:.0f} m" if dist != float("inf") else "yaqinida umuman yo'q"
            print(f"   - {point.lat:.6f}, {point.lon:.6f} ({point.kind}) — {near}")


if __name__ == "__main__":
    main()
