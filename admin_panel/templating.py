"""Shablonlar va statik fayllar yo'li. Yo'llar shu fayl joylashuvidan hisoblanadi,
shuning uchun panel qaysi papkadan ishga tushirilishidan qat'i nazar ishlaydi."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

PANEL_DIR = Path(__file__).resolve().parent
STATIC_DIR = PANEL_DIR / "static"

templates = Jinja2Templates(directory=str(PANEL_DIR / "templates"))
