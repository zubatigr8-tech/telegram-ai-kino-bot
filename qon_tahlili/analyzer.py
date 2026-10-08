"""Qon tahlili natijalarini baholash: normadan chetlanishlar, ehtimoliy kasalliklar,
kelajakdagi xavflar va chora-tadbirlar.

Bu tibbiy tashxis EMAS — qoidalar xalqaro klinik tavsiyalardagi chegaralarga asoslangan
(ADA — diabet, ESC — lipidlar, KDIGO — buyrak, WHO — anemiya) va natijani shifokorga
qanday savol bilan borishni tushuntirish uchun mo'ljallangan.
"""
from dataclasses import dataclass, field
from typing import Optional

from qon_tahlili.parser import ParsedValue

LOW, NORMAL, HIGH = "low", "normal", "high"

# Finding.kind
CURRENT = "current"  # hozirgi holat
RISK = "risk"  # kelajakdagi xavf

# Finding.level
INFO, WARN, URGENT = 1, 2, 3


@dataclass
class MarkerStatus:
    key: str
    name: str
    unit: str
    value: float
    low: Optional[float]
    high: Optional[float]
    status: str
    critical: bool
    note: Optional[str] = None


@dataclass
class Finding:
    title: str
    kind: str
    level: int
    evidence: list[str]
    explanation: str
    measures: list[str] = field(default_factory=list)
    specialist: Optional[str] = None
    tests: list[str] = field(default_factory=list)


@dataclass
class Report:
    sex: str
    age: Optional[int]
    statuses: list[MarkerStatus]
    findings: list[Finding]
    egfr: Optional[float] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def critical(self) -> list[MarkerStatus]:
        return [s for s in self.statuses if s.critical]


def egfr_ckd_epi_2021(creatinine_umol: float, age: int, sex: str) -> float:
    """Koptokchalar filtratsiya tezligi (CKD-EPI 2021, irqsiz formula), ml/min/1.73m²."""
    scr = creatinine_umol / 88.4
    kappa, alpha = (0.7, -0.241) if sex == "f" else (0.9, -0.302)
    egfr = 142 * min(scr / kappa, 1) ** alpha * max(scr / kappa, 1) ** -1.200 * 0.9938 ** age
    if sex == "f":
        egfr *= 1.012
    return round(egfr, 1)


def _status(pv: ParsedValue, sex: str) -> MarkerStatus:
    m = pv.marker
    low, high = m.range_for(sex)
    if low is not None and pv.value < low:
        status = LOW
    elif high is not None and pv.value > high:
        status = HIGH
    else:
        status = NORMAL
    critical = (m.critical_low is not None and pv.value < m.critical_low) or (
        m.critical_high is not None and pv.value > m.critical_high
    )
    return MarkerStatus(m.key, m.name, m.unit, pv.value, low, high, status, critical, pv.note)


class _Ctx:
    """Qoidalar ichida qisqa yozish uchun yordamchi."""

    def __init__(self, statuses: dict[str, MarkerStatus], sex: str, age: Optional[int]):
        self.s, self.sex, self.age = statuses, sex, age

    def v(self, key: str) -> Optional[float]:
        st = self.s.get(key)
        return st.value if st else None

    def low(self, key: str) -> bool:
        return key in self.s and self.s[key].status == LOW

    def high(self, key: str) -> bool:
        return key in self.s and self.s[key].status == HIGH

    def has(self, key: str) -> bool:
        return key in self.s

    def ev(self, *keys: str) -> list[str]:
        out = []
        for k in keys:
            st = self.s.get(k)
            if st:
                arrow = {LOW: "⬇️", HIGH: "⬆️"}.get(st.status, "")
                out.append(f"{st.name}: {_fmt(st.value)} {st.unit} {arrow}".strip())
        return out


def _fmt(x: float) -> str:
    return f"{x:g}".replace(".", ",")


# ---------------------------------------------------------------- qoidalar


def _anemia(c: _Ctx) -> list[Finding]:
    out = []
    hgb = c.v("hgb")
    iron_low = (c.v("ferritin") is not None and c.v("ferritin") < 30) or c.low("iron")
    if c.low("hgb"):
        severity = "og'ir" if hgb < 70 else "o'rta" if hgb < 90 else "yengil"
        level = URGENT if hgb < 70 else WARN
        if (c.v("mcv") is not None and c.v("mcv") < 80) or iron_low or c.low("mch"):
            title = f"Temir tanqisligi anemiyasi ({severity} darajali) ehtimoli"
            expl = ("Gemoglobin past, eritrotsitlar mayda yoki temir zaxirasi kam — bu eng ko'p "
                    "uchraydigan kamqonlik turi. Sababi ko'pincha ovqatda temir yetishmasligi, "
                    "hayz paytida ko'p qon yo'qotish yoki ichakdan yashirin qon ketishi.")
            measures = [
                "Temirga boy ovqatlar: mol go'shti, jigar, dukkaklilar (no'xat, mosh, loviya), ismaloq, grechka",
                "Temirni C vitamini bilan birga iste'mol qiling (limon, apelsin, bulg'or qalampiri, karam)",
                "Ovqatdan keyin 1–2 soat davomida choy va kofe ichmang — ular temir so'rilishini kamaytiradi",
                "Temir preparatlarini faqat shifokor buyurgan doza va muddatda qabul qiling",
            ]
            tests = ["Ferritin", "Zardob temiri va TJSS", "Najasda yashirin qon (ayniqsa 40 yoshdan keyin)"]
        elif (c.v("mcv") is not None and c.v("mcv") > 100) or c.low("b12"):
            title = f"B12 yoki foliy kislotasi tanqisligi anemiyasi ({severity} darajali) ehtimoli"
            expl = ("Gemoglobin past va eritrotsitlar yirik — bu ko'pincha B12 vitamini yoki foliy "
                    "kislotasi yetishmasligida bo'ladi. B12 tanqisligi asab tizimiga ham ta'sir qiladi "
                    "(oyoq-qo'l uvishishi, xotira susayishi).")
            measures = [
                "B12 manbalari: go'sht, baliq, tuxum, sut mahsulotlari",
                "Foliy kislotasi manbalari: ko'k bargli sabzavotlar, dukkaklilar",
                "Spirtli ichimliklarni cheklang",
            ]
            tests = ["Vitamin B12", "Foliy kislotasi", "Retikulotsitlar"]
        else:
            title = f"Kamqonlik (anemiya, {severity} darajali)"
            expl = "Gemoglobin normadan past. Turini aniqlash uchun qo'shimcha tahlillar kerak."
            measures = ["To'liq ovqatlaning: go'sht, dukkaklilar, sabzavot va mevalar"]
            tests = ["Ferritin", "Vitamin B12", "Foliy kislotasi", "Retikulotsitlar", "MCV, MCH"]
        out.append(Finding(title, CURRENT, level, c.ev("hgb", "rbc", "mcv", "mch", "ferritin", "iron", "b12"),
                           expl, measures, "Terapevt yoki gematolog", tests))
    elif c.has("ferritin") and c.v("ferritin") < 30:
        out.append(Finding(
            "Yashirin temir tanqisligi", RISK, INFO, c.ev("ferritin", "hgb"),
            "Gemoglobin hozircha normada, lekin organizmdagi temir zaxirasi kamaygan. "
            "Chora ko'rilmasa, kelajakda temir tanqisligi anemiyasi rivojlanishi mumkin.",
            ["Temirga boy ovqatlar + C vitamini", "Ovqatdan keyin darhol choy ichmang"],
            "Terapevt", ["3 oydan keyin ferritin va gemoglobinni qayta tekshirish"]))
    if c.high("hgb") or c.high("hct"):
        out.append(Finding(
            "Qon quyuqlashishi (eritrotsitoz)", CURRENT, WARN, c.ev("hgb", "rbc", "hct"),
            "Gemoglobin/gematokrit yuqori. Sabablari: suvsizlanish, chekish, o'pka kasalliklari, "
            "baland tog'da yashash, kamdan-kam hollarda suyak iligi kasalligi. Qon quyuqligi "
            "tromb hosil bo'lish xavfini oshiradi.",
            ["Kuniga yetarli suv iching (1,5–2 litr, agar shifokor cheklamagan bo'lsa)", "Chekishni tashlang"],
            "Terapevt", ["Tahlilni yetarli suv ichgan holda qayta topshirish"]))
    return out


def _infection(c: _Ctx) -> list[Finding]:
    out = []
    if c.high("wbc") and (c.high("neut") or not c.has("lymph")):
        out.append(Finding(
            "Bakterial infeksiya yoki yallig'lanish ehtimoli", CURRENT, WARN, c.ev("wbc", "neut", "crp", "esr"),
            "Leykotsitlar (va neytrofillar) oshgan — organizm bakterial infeksiya yoki yallig'lanishga "
            "qarshi kurashayotganini ko'rsatadi (masalan, tomoq, o'pka, siydik yo'llari, tish).",
            ["Isitma, og'riq, yo'tal bo'lsa — shifokorga ko'rining",
             "Antibiotikni o'zingizcha ichmang — faqat shifokor buyrug'i bilan"],
            "Terapevt", ["C-reaktiv oqsil", "Umumiy siydik tahlili"]))
    if c.high("lymph") and not c.high("neut"):
        out.append(Finding(
            "Virusli infeksiya ehtimoli", CURRENT, INFO, c.ev("lymph", "wbc"),
            "Limfotsitlar ulushi oshgan — ko'pincha virusli infeksiya (gripp, ORVI) yoki undan "
            "keyingi tiklanish davrida bo'ladi.",
            ["Dam oling, ko'p suyuqlik iching", "2–3 haftadan keyin tahlilni qayta topshiring"],
            "Terapevt"))
    if c.low("wbc"):
        out.append(Finding(
            "Leykotsitlar kamaygan (leykopeniya)", CURRENT, URGENT if c.s["wbc"].critical else WARN,
            c.ev("wbc", "neut"),
            "Immunitet hujayralari kam — virusli infeksiyalar, ayrim dorilar, autoimmun kasalliklar "
            "yoki suyak iligi faoliyatining susayishi sabab bo'lishi mumkin. Infeksiyalarga moyillik oshadi.",
            ["Kasal odamlar bilan yaqin muloqotdan saqlaning", "Qabul qilayotgan dorilaringizni shifokorga ayting"],
            "Gematolog", ["Umumiy qon tahlilini leykoformula bilan qayta topshirish"]))
    if c.high("eos"):
        out.append(Finding(
            "Allergiya yoki gijja (parazit) ehtimoli", CURRENT, INFO, c.ev("eos"),
            "Eozinofillar oshishi ko'pincha allergik holatlar (allergik rinit, astma, dermatit) "
            "yoki ichak parazitlari (gijja) bilan bog'liq.",
            ["Qo'lni ovqatdan oldin sovunlab yuving, sabzavot-mevalarni yaxshi yuving"],
            "Allergolog yoki infeksionist", ["Najasni gijja tuxumlariga tekshirish", "Umumiy IgE"]))
    crp, esr_high = c.v("crp"), c.high("esr")
    if (crp is not None and crp > 10) or esr_high:
        out.append(Finding(
            "Organizmda faol yallig'lanish belgilari", CURRENT, WARN, c.ev("crp", "esr"),
            "C-reaktiv oqsil va/yoki ECHT oshgan — bu infeksiya, autoimmun (masalan, revmatoid artrit) "
            "yoki boshqa yallig'lanish jarayonidan dalolat. Aniq sababini shifokor topadi.",
            ["Bo'g'imlarda og'riq, uzoq davom etayotgan isitma yoki vazn yo'qotish bo'lsa — albatta ayting"],
            "Terapevt", ["Umumiy qon tahlili (leykoformula)", "Revmatoid omil (bo'g'im og'rig'i bo'lsa)"]))
    elif crp is not None and 3 < crp <= 10:
        out.append(Finding(
            "Surunkali past darajali yallig'lanish", RISK, INFO, c.ev("crp"),
            "CRP 3–10 mg/L oralig'ida bo'lishi yurak-qon tomir kasalliklari xavfining oshganini bildiradi.",
            ["Muntazam jismoniy faollik", "Ortiqcha vazn bo'lsa — kamaytirish", "Chekishni tashlang"],
            "Kardiolog"))
    return out


def _platelets(c: _Ctx) -> list[Finding]:
    out = []
    if c.low("plt"):
        out.append(Finding(
            "Trombotsitlar kamaygan (trombotsitopeniya)", CURRENT, URGENT if c.s["plt"].critical else WARN,
            c.ev("plt"),
            "Trombotsitlar qon ivishi uchun kerak. Kamayganda milk qonashi, ko'karishlar oson paydo bo'ladi.",
            ["Aspirin va og'riq qoldiruvchi (NYaQV) dorilarni shifokorsiz ichmang",
             "Lat yeyish xavfi bor sport turlaridan vaqtincha saqlaning"],
            "Gematolog", ["Umumiy qon tahlilini qayta topshirish", "Koagulogramma"]))
    elif c.high("plt"):
        out.append(Finding(
            "Trombotsitlar oshgan (trombotsitoz)", CURRENT, WARN, c.ev("plt"),
            "Ko'pincha yallig'lanish, temir tanqisligi yoki qon yo'qotishdan keyin vaqtincha bo'ladi. "
            "Uzoq saqlansa, tromb xavfi tufayli tekshirish kerak.",
            ["Yetarli suv iching"], "Gematolog", ["Ferritin", "C-reaktiv oqsil"]))
    return out


def _glucose(c: _Ctx) -> list[Finding]:
    out = []
    glu, a1c = c.v("glucose"), c.v("hba1c")
    lifestyle = [
        "Shakar, shirinliklar, oq non, gazli va shirin ichimliklarni keskin kamaytiring",
        "Har kuni kamida 30 daqiqa tez yurish yoki boshqa jismoniy faollik (haftasiga ≥150 daqiqa)",
        "Ortiqcha vazn bo'lsa, uning 5–7% ini tashlash diabet xavfini sezilarli kamaytiradi",
        "Ko'proq sabzavot, dukkaklilar, to'liq donli mahsulotlar iste'mol qiling",
        "Kechki ovqatni yengil va uyqudan 3 soat oldin qiling",
    ]
    if (glu is not None and glu >= 7.0) or (a1c is not None and a1c >= 6.5):
        level = URGENT if glu is not None and glu >= 15 else WARN
        out.append(Finding(
            "Qandli diabet (2-tur) ehtimoli", CURRENT, level, c.ev("glucose", "hba1c"),
            "Och qoringa glyukoza ≥7,0 mmol/L yoki HbA1c ≥6,5% — diabet mezoniga to'g'ri keladi. "
            "Tashxis uchun tahlil boshqa kuni takrorlanishi kerak. Davolanmagan diabet ko'z, buyrak, "
            "asab va yurak-qon tomirlarini shikastlaydi.",
            lifestyle + ["Qand miqdorini glyukometr bilan muntazam o'lchab boring"],
            "Endokrinolog", ["HbA1c", "Och qoringa glyukozani qayta topshirish", "Kreatinin va siydikda albumin",
                             "Ko'z tubini tekshirish (oftalmolog)"]))
    elif (glu is not None and glu >= 5.6) or (a1c is not None and a1c >= 5.7):
        out.append(Finding(
            "Prediabet — kelajakda qandli diabet xavfi", RISK, WARN, c.ev("glucose", "hba1c"),
            "Qand normadan biroz yuqori, lekin hali diabet emas. Bu bosqichda turmush tarzini "
            "o'zgartirish orqali diabetning oldini olish mumkin — aks holda bir necha yil ichida "
            "2-tur diabet rivojlanish ehtimoli yuqori.",
            lifestyle, "Endokrinolog", ["HbA1c", "Glyukozaga tolerantlik testi (GTT)"]))
    if glu is not None and glu < 3.9:
        out.append(Finding(
            "Qand miqdori past (gipoglikemiya)", CURRENT, URGENT if glu < 2.8 else WARN, c.ev("glucose"),
            "Qand past bo'lsa, bosh aylanishi, terlash, titrash, hushdan ketish bo'lishi mumkin.",
            ["Belgilar bo'lsa, darhol shirin ichimlik yoki 3–4 dona qand iste'mol qiling",
             "Ovqatni o'tkazib yubormang"],
            "Endokrinolog"))
    return out


def _lipids(c: _Ctx) -> list[Finding]:
    out = []
    ldl, chol, tg, hdl = c.v("ldl"), c.v("chol"), c.v("tg"), c.v("hdl")
    bad = c.high("ldl") or c.high("chol") or c.high("tg") or c.low("hdl")
    if not bad:
        return out
    level = WARN
    title = "Dislipidemiya — yurak-qon tomir kasalliklari xavfi"
    expl = ("Qondagi yog'lar (lipidlar) muvozanati buzilgan. Yillar davomida bu qon tomir devorlarida "
            "pilakchalar (ateroskleroz) hosil qiladi va kelajakda infarkt, insult, oyoq tomirlari "
            "torayishi xavfini oshiradi.")
    if ldl is not None and ldl >= 4.9 or chol is not None and chol >= 7.5:
        level = URGENT if ldl is not None and ldl >= 4.9 else WARN
        expl += (" LDL juda yuqori (≥4,9 mmol/L) — irsiy giperxolesterinemiya ehtimolini ham tekshirish "
                 "kerak; yaqin qarindoshlarda erta infarkt bo'lganmi, eslang.")
    if tg is not None and tg >= 5.6:
        expl += " Triglitseridlar juda yuqori — bu oshqozon osti bezi yallig'lanishi (pankreatit) xavfini ham oshiradi."
    out.append(Finding(
        title, RISK, level, c.ev("chol", "ldl", "hdl", "tg"), expl,
        ["Hayvon yog'lari, qovurilgan ovqat, kolbasa, fastfud, margarinni kamaytiring",
         "Paxta/zaytun yog'ini me'yorida, haftasiga 2 marta baliq iste'mol qiling",
         "Kletchatka: sabzavot, meva, suli (ovsyanka), dukkaklilar",
         "Muntazam jismoniy faollik HDL (\"yaxshi\" xolesterin)ni oshiradi",
         "Chekishni tashlang, spirtli ichimliklarni cheklang",
         "Qon bosimini muntazam o'lchab boring"],
        "Kardiolog yoki terapevt",
        ["To'liq lipid profil (agar hammasi topshirilmagan bo'lsa)", "EKG", "Qon bosimi nazorati"]))
    return out


def _metabolic(c: _Ctx) -> list[Finding]:
    criteria = 0
    if c.v("tg") is not None and c.v("tg") >= 1.7:
        criteria += 1
    if c.low("hdl"):
        criteria += 1
    if c.v("glucose") is not None and c.v("glucose") >= 5.6:
        criteria += 1
    if criteria < 2:
        return []
    return [Finding(
        "Metabolik sindrom belgilari", RISK, WARN, c.ev("tg", "hdl", "glucose"),
        "Triglitseridlar, \"yaxshi\" xolesterin va qanddagi o'zgarishlar birgalikda metabolik sindromga "
        "xos. Agar bel aylanasi katta (erkaklarda >94 sm, ayollarda >80 sm) yoki qon bosimi ≥130/85 "
        "bo'lsa, tashxis ehtimoli yanada yuqori. Bu holat kelajakda diabet, infarkt, insult va "
        "jigar yog'lanishi xavfini bir necha barobar oshiradi.",
        ["Bel aylanasini va qon bosimini o'lchang",
         "Vaznni bosqichma-bosqich kamaytiring (oyiga 2–4 kg)",
         "Uyqu 7–8 soat, stressni kamaytirish"],
        "Endokrinolog yoki terapevt", ["HbA1c", "Insulin va HOMA-IR indeksi"])]


def _liver(c: _Ctx) -> list[Finding]:
    out = []
    alt, ast = c.v("alt"), c.v("ast")
    if c.high("alt") or c.high("ast"):
        uln = c.s["alt"].high if c.has("alt") else c.s["ast"].high
        top = max(x for x in (alt, ast) if x is not None)
        level = URGENT if top > 10 * uln else WARN
        expl = ("Jigar fermentlari oshgan — jigar hujayralari zararlanayotganini ko'rsatadi. Eng ko'p "
                "sabablari: jigar yog'lanishi (yog'li gepatoz), virusli gepatit (B, C), spirtli ichimliklar, "
                "ayrim dorilar va o'tlar.")
        if alt and ast and ast / alt > 2:
            expl += " AST/ALT nisbati 2 dan katta — bu ko'pincha spirtli ichimliklar bilan bog'liq zararlanishda uchraydi."
        if c.v("tg") is not None and c.v("tg") >= 1.7 or c.v("glucose") is not None and c.v("glucose") >= 5.6:
            expl += " Triglitserid/qand ham yuqori — jigar yog'lanishi (MASLD) ehtimoli katta."
        out.append(Finding(
            "Jigar hujayralari zararlanishi belgilari", CURRENT, level, c.ev("alt", "ast", "ggt", "bili"), expl,
            ["Spirtli ichimliklarni butunlay to'xtating",
             "Yog'li, qovurilgan, shirin ovqat va shirin ichimliklarni kamaytiring",
             "Shifokor bilan kelishmasdan dori, BAD va giyohlar ichmang",
             "Ortiqcha vaznni kamaytiring"],
            "Gastroenterolog (gepatolog)",
            ["Gepatit B (HBsAg) va gepatit C (anti-HCV) tahlili", "Jigar UZI", "GGT, ishqoriy fosfataza, bilirubin"]))
    if c.high("bili"):
        out.append(Finding(
            "Bilirubin oshgan", CURRENT, WARN, c.ev("bili", "alt", "ast"),
            "Bilirubin oshishi jigar kasalligi, o't yo'llari to'silishi yoki eritrotsitlarning tez "
            "parchalanishi bilan bog'liq bo'lishi mumkin. Faqat biroz oshgan bo'lsa va boshqa ko'rsatkichlar "
            "normada bo'lsa, ko'pincha zararsiz Jilber sindromi bo'ladi.",
            ["Ko'z oqi yoki teri sarg'aysa, siydik to'qlashsa — darhol shifokorga"],
            "Gastroenterolog", ["To'g'ri va bilvosita bilirubin", "Jigar va o't pufagi UZI"]))
    if c.low("albumin"):
        out.append(Finding(
            "Albumin kamaygan", CURRENT, WARN, c.ev("albumin", "protein"),
            "Albumin jigarda ishlab chiqariladi. Kamayishi oqsil yetishmasligi, jigar yoki buyrak "
            "kasalliklari (siydik bilan oqsil yo'qotish) belgisi bo'lishi mumkin.",
            ["Ovqatda yetarli oqsil: go'sht, baliq, tuxum, tvorog, dukkaklilar"],
            "Terapevt", ["Umumiy siydik tahlili (oqsil)", "Jigar sinamalari"]))
    return out


def _kidney(c: _Ctx, egfr: Optional[float]) -> list[Finding]:
    out = []
    kidney_measures = [
        "Qon bosimi va qandni nazoratda tuting — bular buyrakni eng ko'p shikastlaydi",
        "Tuzni kuniga 5 g (1 choy qoshiq) gacha kamaytiring",
        "Og'riq qoldiruvchi (ibuprofen, diklofenak) dorilarni tez-tez ichmang",
        "Yetarli suv iching (agar shifokor cheklamagan bo'lsa)",
    ]
    if egfr is not None and egfr < 60:
        stage = "3a" if egfr >= 45 else "3b" if egfr >= 30 else "4" if egfr >= 15 else "5"
        out.append(Finding(
            f"Buyrak faoliyati pasaygan (SBK {stage}-bosqich ehtimoli)", CURRENT,
            URGENT if egfr < 30 else WARN, c.ev("creat", "urea") + [f"KFT (eGFR): {egfr} ml/min/1.73m²"],
            "Buyraklarning qonni tozalash tezligi pasaygan. Agar bu holat 3 oydan ortiq saqlansa, "
            "surunkali buyrak kasalligi (SBK) deb hisoblanadi. Erta aniqlansa, rivojlanishini sekinlatish mumkin.",
            kidney_measures, "Nefrolog",
            ["3 oydan keyin kreatininni qayta topshirish", "Siydikda albumin/kreatinin nisbati", "Buyrak UZI"]))
    elif c.high("creat"):
        out.append(Finding(
            "Kreatinin oshgan", CURRENT, WARN, c.ev("creat", "urea"),
            "Kreatinin buyrak faoliyatini ko'rsatadi. Oshishi suvsizlanish, ko'p go'sht iste'moli, "
            "kuchli mashg'ulot yoki buyrak faoliyati susayishi bilan bog'liq bo'lishi mumkin.",
            kidney_measures, "Nefrolog", ["Kreatininni qayta topshirish", "Umumiy siydik tahlili"]))
    elif egfr is not None and egfr < 90 and (
        (c.v("glucose") or 0) >= 5.6 or (c.v("hba1c") or 0) >= 5.7 or c.high("uric")
    ):
        out.append(Finding(
            "Kelajakda buyrak faoliyati pasayishi xavfi", RISK, INFO,
            [f"KFT (eGFR): {egfr} ml/min/1.73m²"] + c.ev("glucose", "hba1c", "uric"),
            "Buyrak faoliyati biroz pasaygan va qand/siydik kislotasi kabi xavf omillari bor.",
            kidney_measures, "Terapevt", ["Har yili kreatinin va siydikda albumin"]))
    if c.high("urea") and not c.high("creat"):
        out.append(Finding(
            "Mochevina oshgan", CURRENT, INFO, c.ev("urea"),
            "Ko'pincha suvsizlanish yoki oqsilli ovqatni ko'p iste'mol qilishda bo'ladi.",
            ["Yetarli suv iching"], "Terapevt"))
    if c.high("uric"):
        out.append(Finding(
            "Siydik kislotasi yuqori — podagra va buyrak toshi xavfi", RISK, WARN, c.ev("uric"),
            "Siydik kislotasi uzoq vaqt yuqori bo'lsa, bo'g'imlarda kristallar to'planib podagra "
            "(ayniqsa oyoq bosh barmog'ida kuchli og'riq) va buyrakda tosh paydo bo'lishiga olib keladi.",
            ["Qizil go'sht, jigar, buyrak, sardina, go'shtli sho'rvalarni kamaytiring",
             "Pivo va spirtli ichimliklardan voz keching, shirin gazli ichimliklar va fruktozani cheklang",
             "Kuniga 2 litrgacha suv iching", "Ortiqcha vaznni kamaytiring"],
            "Revmatolog yoki terapevt", ["Buyrak UZI"]))
    return out


def _thyroid(c: _Ctx) -> list[Finding]:
    out = []
    if c.high("tsh"):
        if c.low("ft4"):
            title, expl = "Gipotireoz (qalqonsimon bez faoliyati pasaygan) ehtimoli", (
                "TTG yuqori va erkin T4 past — qalqonsimon bez kam gormon ishlab chiqaryapti. "
                "Belgilari: holsizlik, sovuqqa chidamsizlik, vazn ortishi, soch to'kilishi, qabziyat.")
            level = WARN
        else:
            title, expl = "Subklinik gipotireoz ehtimoli", (
                "TTG biroz oshgan. Bu qalqonsimon bez faoliyati sekin pasayishining boshlanishi bo'lishi "
                "mumkin — kelajakda aniq gipotireoz rivojlanishi mumkin, shuning uchun nazorat kerak.")
            level = INFO if c.v("tsh") < 10 else WARN
        out.append(Finding(title, CURRENT, level, c.ev("tsh", "ft4"), expl,
                           ["Yodlangan tuz ishlating (O'zbekiston yod tanqisligi hududi)",
                            "Gormon preparatlarini faqat endokrinolog buyuradi"],
                           "Endokrinolog", ["Erkin T4", "Anti-TPO antitanachalar", "Qalqonsimon bez UZI"]))
    elif c.low("tsh"):
        if c.high("ft4"):
            title, level = "Gipertireoz (qalqonsimon bez faoliyati oshgan) ehtimoli", WARN
            expl = ("TTG past va erkin T4 yuqori. Belgilari: yurak tez urishi, terlash, qo'l titrashi, "
                    "vazn yo'qotish, asabiylik.")
        else:
            title, level = "Subklinik gipertireoz ehtimoli", INFO
            expl = "TTG past. Qalqonsimon bez faoliyatini aniqlashtirish kerak."
        out.append(Finding(title, CURRENT, level, c.ev("tsh", "ft4"), expl,
                           ["Kofe va energetik ichimliklarni kamaytiring"],
                           "Endokrinolog", ["Erkin T4 va T3", "TTG retseptorlariga antitanachalar", "Qalqonsimon bez UZI"]))
    return out


def _vitamins(c: _Ctx) -> list[Finding]:
    out = []
    vitd = c.v("vitd")
    if vitd is not None and vitd < 30:
        deficient = vitd < 20
        out.append(Finding(
            "D vitamini tanqisligi" if deficient else "D vitamini yetishmovchiligi",
            RISK, WARN if deficient else INFO, c.ev("vitd", "ca"),
            "D vitamini suyaklar, mushaklar va immunitet uchun zarur. Uzoq muddat kam bo'lsa, "
            "kelajakda osteoporoz (suyak mo'rtlashishi), suyak sinishi, mushak kuchsizligi xavfi oshadi.",
            ["Kuniga 15–20 daqiqa quyoshda bo'ling (yuz va qo'llar ochiq, soat 11–15 oralig'ida emas)",
             "Yog'li baliq, tuxum sarig'i, sut mahsulotlari",
             "D vitamini preparati dozasini shifokor tahlilga qarab belgilaydi"],
            "Terapevt yoki endokrinolog", ["Kalsiy", "3 oydan keyin vitamin D ni qayta tekshirish"]))
    if c.low("b12") and not c.low("hgb"):
        out.append(Finding(
            "B12 vitamini tanqisligi", RISK, WARN, c.ev("b12"),
            "Hozircha kamqonlik yo'q, lekin B12 kam. Chora ko'rilmasa, kamqonlik va asab tizimi "
            "shikastlanishi (uvishish, xotira pasayishi) rivojlanishi mumkin. Vegetarianlar, "
            "keksalar va metformin ichuvchilarda ko'p uchraydi.",
            ["Go'sht, baliq, tuxum, sut mahsulotlari"], "Terapevt", ["Foliy kislotasi", "Gomotsistein"]))
    return out


def _electrolytes(c: _Ctx) -> list[Finding]:
    out = []
    for key, low_txt, high_txt in (
        ("k", "Kaliy kam: mushak kuchsizligi, yurak ritmi buzilishi xavfi.",
         "Kaliy ko'p: yurak ritmi buzilishi xavfi, ko'pincha buyrak faoliyati yoki dorilar bilan bog'liq."),
        ("na", "Natriy kam: bosh og'rig'i, holsizlik, og'ir holatda talvasa.",
         "Natriy ko'p: ko'pincha suvsizlanish belgisi."),
        ("ca", "Kalsiy kam: mushak tortishishi, uvishish; D vitamini tanqisligi bilan bog'liq bo'lishi mumkin.",
         "Kalsiy ko'p: qalqonsimon oldi bezi yoki boshqa kasalliklarni tekshirish kerak."),
    ):
        if c.low(key) or c.high(key):
            st = c.s[key]
            out.append(Finding(
                f"{st.name} {'kamaygan' if st.status == LOW else 'oshgan'}", CURRENT,
                URGENT if st.critical else WARN, c.ev(key), low_txt if st.status == LOW else high_txt,
                ["Elektrolit buzilishini faqat shifokor nazoratida tuzatish kerak"],
                "Terapevt", ["EKG", "Elektrolitlarni qayta tekshirish", "Kreatinin"]))
    return out


RULES = (_anemia, _infection, _platelets, _glucose, _lipids, _metabolic, _liver, _thyroid,
         _vitamins, _electrolytes)


def analyze(values: dict[str, ParsedValue], sex: str, age: Optional[int] = None) -> Report:
    """sex: "m" yoki "f"; age: yosh (to'liq yillar)."""
    statuses = {k: _status(pv, sex) for k, pv in values.items()}
    ctx = _Ctx(statuses, sex, age)

    egfr = None
    if "creat" in statuses and age:
        egfr = egfr_ckd_epi_2021(statuses["creat"].value, age, sex)

    findings: list[Finding] = []
    for rule in RULES:
        findings.extend(rule(ctx))
    findings.extend(_kidney(ctx, egfr))
    findings.sort(key=lambda f: (-f.level, f.kind != CURRENT))

    warnings = []
    if age is not None and age < 18:
        warnings.append("Normalar kattalar uchun. Bolalarda normalar yoshga qarab farq qiladi — "
                        "natijani pediatr bilan muhokama qiling.")
    if "creat" in statuses and not age:
        warnings.append("Buyrak filtratsiya tezligini (eGFR) hisoblash uchun yosh kerak.")

    order = list(values)
    return Report(sex, age, [statuses[k] for k in order], findings, egfr, warnings)
