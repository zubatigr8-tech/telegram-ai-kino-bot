"""Geografik hisob-kitoblar: masofa, azimut (yo'nalish), qidiruv chegarasi."""
import math

EARTH_RADIUS_M = 6_371_000
METERS_PER_DEG_LAT = 111_320


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Ikki nuqta orasidagi masofa (metr), haversine formulasi."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """1-nuqtadan 2-nuqtaga yo'nalish: 0 — shimol, 90 — sharq (0..360)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    """Ikki yo'nalish orasidagi eng kichik burchak (0..180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def bbox(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lon, max_lon) — nuqta atrofidagi kvadrat."""
    dlat = radius_m / METERS_PER_DEG_LAT
    dlon = radius_m / (METERS_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
