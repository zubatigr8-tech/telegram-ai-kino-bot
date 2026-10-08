from qon_tahlili.analyzer import CURRENT, RISK, URGENT, analyze, egfr_ckd_epi_2021
from qon_tahlili.parser import from_dict, parse_text
from qon_tahlili.report import TELEGRAM_LIMIT, render


def titles(report):
    return [f.title for f in report.findings]


def test_parse_mixed_languages_and_decimal_commas():
    values = parse_text(
        "Гемоглобин 95 г/л (120-160)\nWBC 7,2 x10^9/l; PLT 250\n"
        "HbA1c 6.1 %\nLDL xolesterin 4,1\nUmumiy xolesterin 6,0\nVitamin B12 180\nСОЭ 25\nT4 erkin 14"
    )
    got = {k: v.value for k, v in values.items()}
    assert got == {"hgb": 95, "wbc": 7.2, "plt": 250, "hba1c": 6.1, "ldl": 4.1, "chol": 6.0,
                   "b12": 180, "esr": 25, "ft4": 14}


def test_parse_skips_direct_bilirubin_and_reference_ranges():
    values = parse_text("To'g'ri bilirubin 5\nUmumiy bilirubin 30 (3,4-20,5)")
    assert values["bili"].value == 30


def test_unit_conversion():
    values = parse_text("Gemoglobin 9.5 g/dL, glucose 126 mg/dL, kreatinin 1.2 mg/dl, cholesterol 240")
    assert values["hgb"].value == 95
    assert values["glucose"].value == 7.0
    assert values["creat"].value == 106.08
    assert round(values["chol"].value, 1) == 6.2
    assert values["hgb"].note


def test_iron_deficiency_anemia():
    report = analyze(parse_text("Gemoglobin 98, MCV 74, ferritin 8"), "f", 30)
    assert any("Temir tanqisligi anemiyasi" in t for t in titles(report))


def test_b12_anemia():
    report = analyze(parse_text("Gemoglobin 100, MCV 108"), "m", 60)
    assert any("B12" in t for t in titles(report))


def test_latent_iron_deficiency_is_future_risk():
    report = analyze(parse_text("Gemoglobin 130, ferritin 12"), "f", 25)
    finding = next(f for f in report.findings if "Yashirin temir" in f.title)
    assert finding.kind == RISK


def test_diabetes_vs_prediabetes():
    assert any("Qandli diabet" in t for t in titles(analyze(parse_text("glyukoza 7.4"), "m", 50)))
    pre = analyze(parse_text("glyukoza 6.0"), "m", 50)
    assert [f.kind for f in pre.findings if "Prediabet" in f.title] == [RISK]


def test_metabolic_syndrome_and_lipids():
    report = analyze(parse_text("TG 2.1, HDL 0.9, glyukoza 5.8, LDL 3.6"), "m", 45)
    t = titles(report)
    assert any("Metabolik sindrom" in x for x in t)
    assert any("Dislipidemiya" in x for x in t)


def test_kidney_egfr():
    assert 55 < egfr_ckd_epi_2021(110, 60, "m") < 70
    report = analyze(parse_text("kreatinin 250"), "m", 65)
    assert report.egfr < 30
    assert any(f.level == URGENT and "Buyrak" in f.title for f in report.findings)


def test_thyroid():
    assert any("Gipotireoz" in t for t in titles(analyze(parse_text("TSH 9.2, erkin T4 8"), "f", 40)))
    assert any("Gipertireoz" in t for t in titles(analyze(parse_text("ТТГ 0.05, fT4 30"), "f", 40)))


def test_infection_patterns():
    bact = analyze(parse_text("leykotsitlar 14, neytrofillar 82, CRP 40"), "m", 30)
    assert any("Bakterial" in t for t in titles(bact))
    assert any("yallig'lanish belgilari" in t for t in titles(bact))
    assert any("Allergiya" in t for t in titles(analyze(parse_text("eozinofillar 9"), "m", 30)))


def test_critical_values_are_urgent_and_rendered():
    report = analyze(parse_text("Gemoglobin 62, kaliy 6.8"), "m", 40)
    assert {s.key for s in report.critical} == {"hgb", "k"}
    assert "SHOSHILINCH" in "".join(render(report))


def test_normal_results():
    report = analyze(parse_text("Gemoglobin 145, leykotsit 6, glyukoza 4.8, ALT 20"), "m", 30)
    assert report.findings == []
    assert "jiddiy chetlanish topilmadi" in render(report)[0]


def test_sex_specific_ranges():
    values = parse_text("Gemoglobin 125")
    assert analyze(values, "f", 30).statuses[0].status == "normal"
    assert analyze(values, "m", 30).statuses[0].status == "low"


def test_from_dict_and_message_size():
    values = from_dict({"hgb": 60, "glucose": 20, "ldl": 6, "alt": 500, "creat": 400, "tsh": 12,
                        "vitd": 10, "uric": 600, "plt": 30, "wbc": 1.5, "crp": 80, "eos": 12, "unknown": 1})
    report = analyze(values, "m", 55)
    assert "unknown" not in {s.key for s in report.statuses}
    assert all(f.kind in (CURRENT, RISK) for f in report.findings)
    messages = render(report)
    assert all(len(m) <= TELEGRAM_LIMIT for m in messages)


def test_vision_parses_structured_output(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from qon_tahlili import vision

    captured = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            text = '{"values": [{"key": "hgb", "value": 101}, {"key": "glucose", "value": 6.3}]}'
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(vision.anthropic, "AsyncAnthropic",
                        lambda: SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages())))
    result = asyncio.run(vision.extract_from_image(b"\xff\xd8fake"))
    assert result == {"hgb": 101, "glucose": 6.3}
    assert captured["output_config"]["format"]["type"] == "json_schema"
    assert captured["messages"][0]["content"][0]["type"] == "image"


def test_vision_disabled_without_key(monkeypatch):
    import asyncio

    import pytest

    from qon_tahlili import vision

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(vision.VisionUnavailable):
        asyncio.run(vision.extract_from_image(b""))
