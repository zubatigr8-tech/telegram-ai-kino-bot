"""Tahlil natijasini Telegram uchun (HTML) chiroyli matnga aylantirish."""
from html import escape as _html_escape

from qon_tahlili.analyzer import CURRENT, HIGH, LOW, RISK, URGENT, WARN, Report

DISCLAIMER = (
    "⚠️ <i>Bu dastur shifokor emas va tashxis qo'ymaydi. Natijalar faqat ma'lumot uchun — "
    "ular asosida o'zingizni davolamang va dori ichmang. Har qanday o'zgarishni shifokor bilan muhokama qiling.</i>"
)

TELEGRAM_LIMIT = 4000

_LEVEL_ICON = {URGENT: "🔴", WARN: "🟠"}


def escape(text: str) -> str:
    return _html_escape(text, quote=False)


def _fmt(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _range(low, high) -> str:
    if low is not None and high is not None:
        return f"{_fmt(low)}–{_fmt(high)}"
    if low is not None:
        return f"&gt;{_fmt(low)}"
    return f"&lt;{_fmt(high)}"


def render(report: Report) -> list[str]:
    """Telegram xabarlari ro'yxatini qaytaradi (har biri 4096 belgidan qisqa)."""
    blocks: list[str] = []

    sex = "erkak" if report.sex == "m" else "ayol"
    age = f", {report.age} yosh" if report.age else ""
    lines = [f"🩸 <b>Qon tahlili natijasi</b> ({sex}{age})", ""]
    for st in report.statuses:
        icon = {LOW: "⬇️", HIGH: "⬆️"}.get(st.status, "✅")
        if st.critical:
            icon = "🚨"
        line = f"{icon} {escape(st.name)}: <b>{_fmt(st.value)}</b> {st.unit} <i>(norma {_range(st.low, st.high)})</i>"
        if st.note:
            line += f" — <i>{escape(st.note)}</i>"
        lines.append(line)
    if report.egfr is not None:
        lines.append(f"🧮 Buyrak filtratsiya tezligi (eGFR): <b>{_fmt(report.egfr)}</b> ml/min/1.73m² <i>(norma ≥90)</i>")
    blocks.append("\n".join(lines))

    if report.critical or any(f.level == URGENT for f in report.findings):
        blocks.append(
            "🚨 <b>SHOSHILINCH!</b> Ayrim ko'rsatkichlar xavfli darajada. Bugunning o'zida shifokorga "
            "murojaat qiling. Ahvolingiz og'ir bo'lsa (hushdan ketish, kuchli holsizlik, nafas qisishi, "
            "ko'krakda og'riq) — <b>103</b> ga qo'ng'iroq qiling."
        )

    current = [f for f in report.findings if f.kind == CURRENT]
    risks = [f for f in report.findings if f.kind == RISK]

    if not report.findings:
        blocks.append("✅ <b>Kiritilgan ko'rsatkichlarda jiddiy chetlanish topilmadi.</b>\n"
                      "Sog'lom turmush tarzini davom ettiring va tahlillarni yiliga kamida 1 marta topshiring.")

    for header, items in (("🔎 <b>Hozirgi holat — ehtimoliy sabablar</b>", current),
                          ("🔮 <b>Kelajakdagi xavflar</b>", risks)):
        if not items:
            continue
        blocks.append(header)
        for f in items:
            icon = _LEVEL_ICON.get(f.level, "🟡")
            part = [f"{icon} <b>{escape(f.title)}</b>"]
            if f.evidence:
                part.append("📊 " + escape("; ".join(f.evidence)))
            part.append(escape(f.explanation))
            if f.measures:
                part.append("🛡 <b>Nima qilish kerak:</b>")
                part.extend(f"  • {escape(m)}" for m in f.measures)
            if f.specialist:
                part.append(f"👨‍⚕️ <b>Shifokor:</b> {escape(f.specialist)}")
            if f.tests:
                part.append(f"🧪 <b>Qo'shimcha tahlillar:</b> {escape(', '.join(f.tests))}")
            blocks.append("\n".join(part))

    for w in report.warnings:
        blocks.append(f"ℹ️ {escape(w)}")
    blocks.append(DISCLAIMER)
    return _pack(blocks)


def _pack(blocks: list[str]) -> list[str]:
    """Bloklarni Telegram chegarasidan oshmaydigan xabarlarga yig'adi."""
    messages, current = [], ""
    for block in blocks:
        while len(block) > TELEGRAM_LIMIT:  # juda uzun blok (amalda bo'lmaydi) — qatorlab bo'lamiz
            cut = block.rfind("\n", 0, TELEGRAM_LIMIT)
            cut = cut if cut > 0 else TELEGRAM_LIMIT
            if current:
                messages.append(current)
                current = ""
            messages.append(block[:cut])
            block = block[cut:].lstrip("\n")
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > TELEGRAM_LIMIT:
            messages.append(current)
            current = block
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages
