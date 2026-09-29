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


# --- Ovozli ogohlantirish ---

import asyncio
from types import SimpleNamespace

from antiradar.alerts import Alert
from antiradar.voice import VoiceSender


class FakeBot:
    def __init__(self, fail_voice=False):
        self.calls = []
        self.fail_voice = fail_voice

    async def send_voice(self, chat_id, voice):
        if self.fail_voice:
            raise RuntimeError("VOICE_MESSAGES_FORBIDDEN")
        self.calls.append(("voice", voice if isinstance(voice, str) else "upload"))
        return SimpleNamespace(voice=SimpleNamespace(file_id="FILE123"))

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append(("text", text))


def make_sender(tmp_path, counter):
    async def synth(text, lang, path):
        counter.append((lang, text))
        path.write_bytes(b"mp3")

    return VoiceSender(tmp_path, synthesize=synth)


def test_voice_is_generated_once_then_file_id_reused(tmp_path):
    synth_calls = []
    sender = make_sender(tmp_path, synth_calls)
    bot = FakeBot()

    async def run():
        assert await sender.send(bot, 1, "uz", "Diqqat!")
        assert await sender.send(bot, 2, "uz", "Diqqat!")

    asyncio.run(run())
    assert synth_calls == [("uz", "Diqqat!")]
    assert bot.calls == [("voice", "upload"), ("voice", "FILE123")]


def test_voice_failure_returns_false(tmp_path):
    async def broken(text, lang, path):
        raise ConnectionError("TTS down")

    sender = VoiceSender(tmp_path, synthesize=broken)
    assert asyncio.run(sender.send(FakeBot(), 1, "uz", "x")) is False
    assert asyncio.run(make_sender(tmp_path, []).send(FakeBot(fail_voice=True), 1, "uz", "y")) is False


def test_voice_warmup_stops_after_repeated_failures(tmp_path):
    calls = []

    async def broken(text, lang, path):
        calls.append(text)
        raise ConnectionError("TTS down")

    sender = VoiceSender(tmp_path, synthesize=broken)
    assert asyncio.run(sender.warmup([("uz", str(i)) for i in range(10)])) == 0
    assert len(calls) == 3


def test_notify_sends_voice_before_text(tmp_path, monkeypatch):
    from antiradar.handlers import location

    monkeypatch.setattr(location, "voice_sender", make_sender(tmp_path, []))
    bot = FakeBot()
    asyncio.run(location.notify(bot, 1, "uz", "ovoz", "matn"))
    assert [kind for kind, _ in bot.calls] == ["voice", "text"]

    # Ovoz ishlamasa ham matn baribir yuboriladi
    bot = FakeBot(fail_voice=True)
    asyncio.run(location.notify(bot, 1, "uz", "ovoz", "matn"))
    assert bot.calls == [("text", "matn")]


def test_voice_text_uses_threshold_not_exact_distance():
    from antiradar.handlers.location import alert_voice_text

    cam = CameraPoint(id=1, lat=0, lon=0, kind="fixed", speed_limit=60)
    alert = Alert(camera=cam, distance_m=437.2, threshold_m=500, overspeed=True)
    text = alert_voice_text("uz", alert)
    assert text == "Diqqat! 500 metrdan keyin Tezlik kamerasi. Tezlik chegarasi 60. Tezlikni kamaytiring!"


# --- Yo'l belgilari ---

from antiradar.alerts import RADAR_KINDS, SIGN_KINDS
from antiradar.osm_import import parse_kind


def test_sign_alerts_once_at_150m():
    sign = CameraPoint(id=7, lat=north(600), lon=LON, kind="crossing")
    got = drive(TrackState(), [sign], [0, 100, 200, 300, 400, 460, 500, 550])
    assert len(got) == 1
    assert got[0].threshold_m == 150 and got[0].distance_m <= 150


def test_radar_and_sign_together():
    radar = CameraPoint(id=1, lat=north(700), lon=LON, speed_limit=60)
    sign = CameraPoint(id=2, lat=north(650), lon=LON, kind="speed_limit", speed_limit=60)
    got = drive(TrackState(), [radar, sign], [0, 100, 250, 400, 520, 560])
    # Radar: 500 va 200 m da; belgi: faqat 150 m da (yaqinrog'i birinchi aytiladi)
    assert [(a.camera.id, a.threshold_m) for a in got] == [(1, 500), (2, 150), (1, 200)]


def test_osm_sign_kinds():
    assert parse_kind({"highway": "speed_camera"}) == "fixed"
    assert parse_kind({"highway": "crossing"}) == "crossing"
    assert parse_kind({"highway": "crossing", "crossing": "no"}) is None
    assert parse_kind({"highway": "stop"}) == "stop"
    assert parse_kind({"highway": "give_way"}) == "give_way"
    assert parse_kind({"traffic_calming": "bump"}) == "speed_bump"
    assert parse_kind({"traffic_calming": "island"}) is None
    assert parse_kind({"railway": "level_crossing"}) == "railway_crossing"
    assert parse_kind({"hazard": "children"}) == "children"
    assert parse_kind({"traffic_sign": "UZ:3.24", "maxspeed": "40"}) == "speed_limit"


def test_every_kind_has_translation():
    for code in LANGUAGES:
        for kind in RADAR_KINDS + SIGN_KINDS:
            assert t(code, f"kind_{kind}") != f"kind_{kind}", (code, kind)


# --- Fayldan import ---

from antiradar.file_import import parse_csv


def test_csv_import_parsing():
    text = "﻿lat;lon;turi;limit\n41,311;69,279;fixed;60\n41.2;69.1;crossing;\nabc;1;fixed;\n41;69;ufo;\n"
    points, errors = parse_csv(text)
    assert [(p.lat, p.lon, p.kind, p.speed_limit) for p in points] == [
        (41.311, 69.279, "fixed", 60),
        (41.2, 69.1, "crossing", None),
    ]
    assert len(errors) == 2


def test_csv_without_coordinates():
    points, errors = parse_csv("name,city\nx,y\n")
    assert points == [] and errors
