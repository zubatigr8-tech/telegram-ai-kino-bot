"""Erkin matndan ("Gemoglobin 95, ALT 56 U/L, glyukoza 6,8 ...") ko'rsatkich qiymatlarini ajratib olish."""
import re
from dataclasses import dataclass

from qon_tahlili.markers import BY_KEY, MARKERS, Marker

_LETTERS = "a-zа-яёўқғҳʼ'"
_DIGIT_TO_LETTER = str.maketrans("0123456789", "abcdefghij")


def _placeholder(key: str) -> str:
    # Raqamli nomlar ("HbA1c", "B12", "T4") matnni "nom → son" bo'laklariga ajratishga xalaqit
    # beradi, shuning uchun ularni oldindan raqamsiz belgiga almashtiramiz.
    return f" qqq{key.translate(_DIGIT_TO_LETTER)}qqq "


# Raqamli taxalluslar: uzunlari birinchi ("ft4" "t4"dan oldin)
_DIGIT_ALIASES = sorted(
    ((alias, m.key) for m in MARKERS for alias in m.aliases if re.search(r"\d", alias)),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_SEGMENT_RE = re.compile(r"([^\d\n;]+?)\s*(\d+(?:[.,]\d+)?)")


@dataclass
class ParsedValue:
    marker: Marker
    value: float
    raw: float
    note: str | None = None


def _normalize(text: str) -> str:
    text = text.lower()
    for ch in "ʻʼ’`‘":
        text = text.replace(ch, "'")
    for alias, key in _DIGIT_ALIASES:
        pattern = rf"(?<![{_LETTERS}0-9]){re.escape(alias)}(?![{_LETTERS}0-9])"
        text = re.sub(pattern, _placeholder(key), text)
    return text


def _alias_patterns(marker: Marker) -> list[tuple[re.Pattern, int]]:
    result = []
    for alias in marker.aliases:
        token = _placeholder(marker.key).strip() if re.search(r"\d", alias) else alias
        pattern = re.compile(rf"(?<![{_LETTERS}]){re.escape(token)}(?![{_LETTERS}])")
        result.append((pattern, len(alias)))
    return result


_PATTERNS = {m.key: _alias_patterns(m) for m in MARKERS}


def _match_marker(label: str) -> Marker | None:
    best: tuple[int, int, int] | None = None  # (priority, alias uzunligi, -joylashuv)
    best_marker = None
    for marker in MARKERS:
        if any(word in label for word in marker.exclude):
            continue
        for pattern, length in _PATTERNS[marker.key]:
            match = pattern.search(label)
            if match:
                score = (marker.priority, length, match.start())
                if best is None or score > best:
                    best, best_marker = score, marker
    return best_marker


def parse_text(text: str) -> dict[str, ParsedValue]:
    """Matndagi har bir tanilgan ko'rsatkichning birinchi qiymatini qaytaradi."""
    normalized = _normalize(text)
    results: dict[str, ParsedValue] = {}
    for label, number in _SEGMENT_RE.findall(normalized):
        marker = _match_marker(label)
        if marker is None or marker.key in results:
            continue
        raw = float(number.replace(",", "."))
        value, note = marker.convert(raw) if marker.convert else (raw, None)
        results[marker.key] = ParsedValue(marker, value, raw, note)
    return results


def from_dict(values: dict[str, float]) -> dict[str, ParsedValue]:
    """Tayyor {kalit: qiymat} lug'atidan (masalan rasmdan o'qilgan) natija yasaydi."""
    results = {}
    for key, raw in values.items():
        marker = BY_KEY.get(key)
        if marker is None or raw is None:
            continue
        value, note = marker.convert(raw) if marker.convert else (raw, None)
        results[key] = ParsedValue(marker, value, raw, note)
    return results
