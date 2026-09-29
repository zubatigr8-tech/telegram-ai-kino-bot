"""Ko'p tillilik: matnlar antiradar/locales/<til>.json fayllarida saqlanadi."""
import json
from pathlib import Path

LOCALES_DIR = Path(__file__).resolve().parent / "locales"

# Tanlash tugmalarida ko'rinadigan tartib
LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "tr": "🇹🇷 Türkçe",
}
DEFAULT_LANG = "uz"

_texts: dict[str, dict[str, str]] = {
    code: json.loads((LOCALES_DIR / f"{code}.json").read_text(encoding="utf-8")) for code in LANGUAGES
}


def detect_lang(telegram_code: str | None) -> str:
    """Telegram ilovasining tilidan (masalan 'ru', 'en-US') mos tilni tanlaydi."""
    code = (telegram_code or "").split("-")[0].lower()
    return code if code in LANGUAGES else DEFAULT_LANG


def t(lang: str | None, key: str, **kwargs) -> str:
    texts = _texts.get(lang or DEFAULT_LANG, _texts[DEFAULT_LANG])
    text = texts.get(key) or _texts[DEFAULT_LANG].get(key) or key
    return text.format(**kwargs) if kwargs else text


def all_variants(key: str) -> set[str]:
    """Kalitning barcha tillardagi matni — menyu tugmasini qaysi tilda bosilsa ham tanish uchun."""
    return {texts[key] for texts in _texts.values() if key in texts}
