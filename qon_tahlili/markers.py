"""Qon tahlili ko'rsatkichlari: nomlari (uz/ru/en), o'lchov birligi, kattalar uchun normalar,
xavfli (kritik) chegaralar va boshqa birlikda kiritilgan qiymatni avtomatik o'girish.

Normalar MDH/O'zbekiston laboratoriyalarida keng tarqalgan SI birliklarida berilgan.
Laboratoriyalar orasida normalar biroz farq qilishi mumkin — bu dastur faqat yo'naltiruvchi.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

# (qiymat) -> (o'girilgan qiymat, izoh yoki None)
Converter = Callable[[float], tuple[float, Optional[str]]]


@dataclass(frozen=True)
class Marker:
    key: str
    name: str  # foydalanuvchiga ko'rsatiladigan nom
    unit: str
    aliases: tuple[str, ...]
    # (past, yuqori) chegara; None — chegara yo'q. Erkak/ayol uchun alohida bo'lishi mumkin.
    male: tuple[Optional[float], Optional[float]]
    female: tuple[Optional[float], Optional[float]]
    critical_low: Optional[float] = None
    critical_high: Optional[float] = None
    convert: Optional[Converter] = None
    # Umumiy nomli ko'rsatkichlar (masalan "xolesterin") aniqroq nomlardan ("LDL xolesterin") keyin tanlanadi
    priority: int = 1
    # Shu so'zlar bo'lsa, bu ko'rsatkich emas (masalan "to'g'ri bilirubin" — umumiy bilirubin emas)
    exclude: tuple[str, ...] = field(default_factory=tuple)

    def range_for(self, sex: str) -> tuple[Optional[float], Optional[float]]:
        return self.female if sex == "f" else self.male


def _if_below(threshold: float, factor: float, note: str) -> Converter:
    def conv(v: float) -> tuple[float, Optional[str]]:
        if v < threshold:
            return round(v * factor, 2), note
        return v, None
    return conv


def _if_above(threshold: float, divisor: float, note: str) -> Converter:
    def conv(v: float) -> tuple[float, Optional[str]]:
        if v > threshold:
            return round(v / divisor, 2), note
        return v, None
    return conv


MARKERS: list[Marker] = [
    # --- Umumiy qon tahlili ---
    Marker("hgb", "Gemoglobin", "g/L",
           ("gemoglobin", "hemoglobin", "haemoglobin", "hgb", "hb", "гемоглобин"),
           male=(130, 170), female=(120, 150), critical_low=70, critical_high=200,
           convert=_if_below(25, 10, "g/dL dan g/L ga o'girildi"), priority=0),
    Marker("rbc", "Eritrotsitlar", "×10¹²/L",
           ("eritrotsit", "eritrotsitlar", "erythrocytes", "rbc", "эритроциты", "эритроцит"),
           male=(4.3, 5.7), female=(3.8, 5.1)),
    Marker("hct", "Gematokrit", "%",
           ("gematokrit", "hematocrit", "hct", "гематокрит"),
           male=(39, 49), female=(35, 45), convert=_if_below(1, 100, "ulushdan foizga o'girildi")),
    Marker("mcv", "MCV (eritrotsit hajmi)", "fL", ("mcv",), male=(80, 100), female=(80, 100)),
    Marker("mch", "MCH (eritrotsitdagi gemoglobin)", "pg", ("mch",), male=(27, 34), female=(27, 34)),
    Marker("wbc", "Leykotsitlar", "×10⁹/L",
           ("leykotsit", "leykotsitlar", "leukocytes", "wbc", "лейкоциты", "лейкоцит"),
           male=(4.0, 9.0), female=(4.0, 9.0), critical_low=2.0, critical_high=30),
    Marker("neut", "Neytrofillar", "%",
           ("neytrofil", "neytrofillar", "neutrophils", "neut", "neu", "нейтрофилы", "сегментоядерные"),
           male=(47, 72), female=(47, 72)),
    Marker("lymph", "Limfotsitlar", "%",
           ("limfotsit", "limfotsitlar", "lymphocytes", "lymph", "lym", "лимфоциты"),
           male=(19, 37), female=(19, 37)),
    Marker("mono", "Monotsitlar", "%",
           ("monotsit", "monotsitlar", "monocytes", "mono", "mon", "моноциты"),
           male=(3, 11), female=(3, 11)),
    Marker("eos", "Eozinofillar", "%",
           ("eozinofil", "eozinofillar", "eosinophils", "eos", "эозинофилы"),
           male=(0.5, 5), female=(0.5, 5)),
    Marker("plt", "Trombotsitlar", "×10⁹/L",
           ("trombotsit", "trombotsitlar", "platelets", "plt", "тромбоциты"),
           male=(150, 400), female=(150, 400), critical_low=50, critical_high=1000),
    Marker("esr", "ECHT (SOE)", "mm/soat",
           ("echt", "soe", "esr", "соэ", "сое"),
           male=(2, 15), female=(2, 20)),

    # --- Qand almashinuvi ---
    Marker("glucose", "Glyukoza (och qoringa)", "mmol/L",
           ("glyukoza", "glukoza", "glucose", "glu", "qand", "глюкоза", "сахар"),
           male=(3.9, 5.5), female=(3.9, 5.5), critical_low=2.8, critical_high=25,
           convert=_if_above(35, 18, "mg/dL dan mmol/L ga o'girildi")),
    Marker("hba1c", "Glikirlangan gemoglobin (HbA1c)", "%",
           ("hba1c", "glikirlangan gemoglobin", "glikozillangan gemoglobin", "гликированный гемоглобин"),
           male=(4.0, 5.6), female=(4.0, 5.6)),

    # --- Lipidlar ---
    Marker("chol", "Umumiy xolesterin", "mmol/L",
           ("xolesterin", "holesterin", "cholesterol", "chol", "холестерин"),
           male=(None, 5.2), female=(None, 5.2),
           convert=_if_above(20, 38.67, "mg/dL dan mmol/L ga o'girildi"), priority=0),
    Marker("ldl", "LDL xolesterin (\"yomon\")", "mmol/L",
           ("ldl", "lpnp", "лпнп", "zichligi past"),
           male=(None, 3.0), female=(None, 3.0),
           convert=_if_above(15, 38.67, "mg/dL dan mmol/L ga o'girildi")),
    Marker("hdl", "HDL xolesterin (\"yaxshi\")", "mmol/L",
           ("hdl", "lpvp", "лпвп", "zichligi yuqori"),
           male=(1.0, None), female=(1.2, None),
           convert=_if_above(5, 38.67, "mg/dL dan mmol/L ga o'girildi")),
    Marker("tg", "Triglitseridlar", "mmol/L",
           ("triglitserid", "triglitseridlar", "triglyceride", "triglycerides", "tg", "триглицериды"),
           male=(None, 1.7), female=(None, 1.7),
           convert=_if_above(20, 88.57, "mg/dL dan mmol/L ga o'girildi")),

    # --- Jigar ---
    Marker("alt", "ALT (ALaT)", "U/L", ("alt", "alat", "алт", "алат"), male=(None, 41), female=(None, 33)),
    Marker("ast", "AST (ASaT)", "U/L", ("ast", "asat", "аст", "асат"), male=(None, 40), female=(None, 32)),
    Marker("ggt", "GGT", "U/L", ("ggt", "ggtp", "ггт", "ггтп"), male=(None, 55), female=(None, 38)),
    Marker("alp", "Ishqoriy fosfataza", "U/L",
           ("ishqoriy fosfataza", "alp", "щелочная фосфатаза"), male=(40, 130), female=(35, 105)),
    Marker("bili", "Umumiy bilirubin", "µmol/L",
           ("bilirubin", "билирубин"), male=(3.4, 20.5), female=(3.4, 20.5),
           exclude=("to'g'ri", "bevosita", "bilvosita", "direct", "прямой", "непрямой", "связанный")),
    Marker("protein", "Umumiy oqsil", "g/L",
           ("umumiy oqsil", "oqsil", "total protein", "общий белок", "белок"), male=(64, 83), female=(64, 83)),
    Marker("albumin", "Albumin", "g/L", ("albumin", "альбумин"), male=(35, 52), female=(35, 52)),

    # --- Buyrak ---
    Marker("creat", "Kreatinin", "µmol/L",
           ("kreatinin", "creatinine", "crea", "креатинин"),
           male=(62, 106), female=(44, 80), critical_high=500,
           convert=_if_below(20, 88.4, "mg/dL dan µmol/L ga o'girildi")),
    Marker("urea", "Mochevina", "mmol/L",
           ("mochevina", "siydikchil", "urea", "bun", "мочевина"), male=(2.5, 8.3), female=(2.5, 8.3)),
    Marker("uric", "Siydik kislotasi", "µmol/L",
           ("siydik kislotasi", "siydik kislota", "uric acid", "мочевая кислота"),
           male=(210, 420), female=(150, 350),
           convert=_if_below(20, 59.48, "mg/dL dan µmol/L ga o'girildi")),

    # --- Qalqonsimon bez ---
    Marker("tsh", "TTG (TSH)", "mIU/L", ("ttg", "tsh", "ттг"), male=(0.4, 4.0), female=(0.4, 4.0)),
    Marker("ft4", "Erkin T4", "pmol/L",
           ("erkin t4", "t4 erkin", "ft4", "t4", "свободный т4", "т4 свободный", "т4"),
           male=(10, 22), female=(10, 22)),

    # --- Vitaminlar, temir ---
    Marker("ferritin", "Ferritin", "ng/mL", ("ferritin", "ферритин"), male=(30, 400), female=(15, 150)),
    Marker("iron", "Zardob temiri", "µmol/L",
           ("temir", "zardob temiri", "serum iron", "iron", "железо", "сывороточное железо"),
           male=(11.6, 31.3), female=(9.0, 30.4)),
    Marker("b12", "Vitamin B12", "pg/mL",
           ("vitamin b12", "b12", "в12", "витамин в12", "кобаламин"), male=(200, 900), female=(200, 900)),
    Marker("vitd", "Vitamin D (25-OH)", "ng/mL",
           ("vitamin d3", "vitamin d", "25(oh)d3", "25(oh)d", "25-oh", "витамин d3", "витамин d", "витамин д"), male=(30, 100), female=(30, 100)),

    # --- Yallig'lanish, elektrolitlar ---
    Marker("crp", "C-reaktiv oqsil (SRO)", "mg/L",
           ("crp", "c-reaktiv", "sro", "srb", "срб", "с-реактивный белок"), male=(None, 5), female=(None, 5)),
    Marker("k", "Kaliy", "mmol/L", ("kaliy", "potassium", "калий"),
           male=(3.5, 5.1), female=(3.5, 5.1), critical_low=2.8, critical_high=6.2),
    Marker("na", "Natriy", "mmol/L", ("natriy", "sodium", "натрий"),
           male=(136, 145), female=(136, 145), critical_low=120, critical_high=160),
    Marker("ca", "Kalsiy", "mmol/L", ("kalsiy", "kalciy", "calcium", "кальций"),
           male=(2.15, 2.55), female=(2.15, 2.55), critical_low=1.75, critical_high=3.4),
]

BY_KEY: dict[str, Marker] = {m.key: m for m in MARKERS}
