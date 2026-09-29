import json

import pytest

from antiradar import alerts
from antiradar.alerts import CameraPoint, TrackState, personal_overspeed, pick_alerts, update_motion
from antiradar.geo import angle_diff, bearing_deg, distance_m
from antiradar.i18n import LANGUAGES, LOCALES_DIR, detect_lang, t
from antiradar.osm_import import parse_direction, parse_maxspeed

# Toshkent atrofidagi nuqtalar; ~0.0009° kenglik ≈ 100 m
LAT, LON = 41.30, 69.24
M = 1 / 111_320  # 1 metr kenglik bo'yicha, gradusda


def north(meters: float) -> float:
    return LAT + meters * M


def drive(state: TrackState, cams, points, start_ts=0.0, step_s=5.0, heading=0.0):
    """Shimol tomonga harakatni simulyatsiya qiladi, barcha ogohlantirishlarni qaytaradi."""
    result = []
    for i, meters in enumerate(points):
        update_motion(state, north(meters), LON, start_ts + i * step_s, heading)
        result.extend(pick_alerts(state, cams))
    return result


def test_geo_basics():
    assert distance_m(LAT, LON, north(1000), LON) == pytest.approx(1000, rel=0.01)
    assert bearing_deg(LAT, LON, north(100), LON) == pytest.approx(0, abs=0.5)
    assert bearing_deg(LAT, LON, LAT, LON + 0.01) == pytest.approx(90, abs=0.5)
    assert angle_diff(350, 10) == 20
    assert angle_diff(0, 180) == 180


def test_alerts_at_each_threshold_once():
    cam = CameraPoint(id=1, lat=north(2000), lon=LON, speed_limit=60)
    got = drive(TrackState(), [cam], [1400, 1550, 1600, 1700, 1850, 1900, 1950])
    assert [round(a.distance_m, -1) for a in got] == [450, 150]


def test_camera_behind_is_ignored():
    cam = CameraPoint(id=1, lat=north(-300), lon=LON)  # orqada
    assert drive(TrackState(), [cam], [0, 50, 100]) == []


def test_camera_for_opposite_direction_is_ignored():
    cam = CameraPoint(id=1, lat=north(400), lon=LON, direction=180)  # janubga harakatni o'lchaydi
    assert drive(TrackState(), [cam], [0, 100, 250]) == []
    cam_same = CameraPoint(id=2, lat=north(400), lon=LON, direction=0)
    assert len(drive(TrackState(), [cam_same], [0, 100, 250])) == 2


def test_heading_from_movement_when_telegram_gives_none():
    cam = CameraPoint(id=1, lat=north(-400), lon=LON)
    state = TrackState()
    # Janubga harakat: kamera oldinda bo'ladi
    for i, meters in enumerate([0, -100, -250]):
        update_motion(state, north(meters), LON, i * 5.0, None)
    assert state.heading == pytest.approx(180, abs=1)
    assert pick_alerts(state, [cam])


def test_alert_repeats_after_leaving_and_coming_back():
    cam = CameraPoint(id=1, lat=north(300), lon=LON)
    state = TrackState()
    assert drive(state, [cam], [0, 150])
    # uzoqlashdik (kamera qidiruvdan chiqib ketdi) — hisob tozalanadi
    update_motion(state, north(-1500), LON, 100, 0)
    assert pick_alerts(state, []) == []
    assert state.alerted == {}
    assert drive(state, [cam], [0, 150], start_ts=200)


def test_speed_and_overspeed():
    cam = CameraPoint(id=1, lat=north(700), lon=LON, speed_limit=60)
    state = TrackState()
    # 5 soniyada 125 m = 90 km/soat
    got = drive(state, [cam], [0, 125, 250])
    assert state.speed_kmh == pytest.approx(90, rel=0.02)
    assert got and got[0].overspeed


def test_gps_jump_is_not_speed():
    state = TrackState()
    update_motion(state, LAT, LON, 0, 0)
    update_motion(state, north(5000), LON, 5, 0)  # 5 soniyada 5 km — sakrash
    assert state.speed_kmh is None


def test_personal_overspeed_cooldown():
    state = TrackState(speed_kmh=100)
    assert personal_overspeed(state, 90, now=1000)
    assert not personal_overspeed(state, 90, now=1030)
    assert personal_overspeed(state, 90, now=1000 + alerts.PERSONAL_OVERSPEED_COOLDOWN_S + 1)
    assert not personal_overspeed(state, None, now=5000)


def test_locales_have_same_keys():
    keys = {code: set(json.loads((LOCALES_DIR / f"{code}.json").read_text("utf-8"))) for code in LANGUAGES}
    for code, k in keys.items():
        assert k == keys["uz"], code


def test_i18n_helpers():
    assert detect_lang("ru") == "ru"
    assert detect_lang("en-US") == "en"
    assert detect_lang("de") == "uz"
    assert detect_lang(None) == "uz"
    assert "5" in t("tr", "sub_offer", price=5)


def test_osm_parsers():
    assert parse_maxspeed("60") == 60
    assert parse_maxspeed("30 mph") == 48
    assert parse_maxspeed("none") is None
    assert parse_direction("NE") == 45
    assert parse_direction("370") == 10
    assert parse_direction("forward") is None
