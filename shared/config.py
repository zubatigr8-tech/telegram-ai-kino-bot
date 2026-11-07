"""Loyihaning barcha sozlamalari shu yerda, .env faylidan o'qiladi."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _split_ids(raw: str) -> set[int]:
    result = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result


# Doimiy disk: Railway Volume ulanganda RAILWAY_VOLUME_MOUNT_PATH o'zgaruvchisini Railway o'zi beradi;
# boshqa hostinglarda odatda /data. Doimiy disk bo'lmasa — baza har deployda O'CHIB KETADI.
PERSISTENT_DIR: str | None = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or ("/data" if os.path.isdir("/data") else None)
_DATA_DIR = Path(PERSISTENT_DIR) if PERSISTENT_DIR else BASE_DIR
ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT_NAME") or os.getenv("RAILWAY_SERVICE_ID"))


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: set[int] = _split_ids(os.getenv("ADMIN_IDS", ""))

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite+aiosqlite:///{_DATA_DIR / 'bot_database.db'}"
    )
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", str(_DATA_DIR / "backups"))

    # --- Media yuklash (Instagram / YouTube / TikTok) ---
    # Vaqtinchalik yuklab olingan fayllar papkasi (yuborilgach o'chiriladi)
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))
    # Bir vaqtda nechta yuklash bajarilsin (server kuchiga qarab)
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    # Oddiy Bot API 50 MB gacha fayl yuborishga ruxsat beradi
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))
    # Bundan uzun videolar yuklanmaydi (soniya)
    MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "1200"))
    # Instagram/YouTube ba'zan login so'raydi — shunda brauzerdan eksport qilingan
    # cookies.txt (Netscape formatida) yo'lini ko'rsating. Ixtiyoriy.
    COOKIES_FILE: str = os.getenv("COOKIES_FILE", "")
    # Hostingda fayl yuklab bo'lmaydi — cookies.txt ning ICHIDAGI matnini shu o'zgaruvchiga qo'yish mumkin
    COOKIES_TEXT: str = os.getenv("COOKIES_TEXT", "")
    # Admin botga yuborgan cookies fayllari shu papkada saqlanadi. Hostingda doimiy diskda (/data)
    # bo'lishi kerak, aks holda har deploy'da o'chib ketadi.
    COOKIES_DIR: str = os.getenv(
        "COOKIES_DIR", str(_DATA_DIR / "cookies")
    )
    # Kompyuter/server Telegram yoki YouTube'ga to'g'ridan-to'g'ri ulana olmasa — proksi.
    # Masalan: socks5://127.0.0.1:1080 yoki http://user:pass@host:port. Ixtiyoriy.
    PROXY_URL: str = os.getenv("PROXY_URL", "").strip()

    # --- Kanalga qo'shilish so'rovlari (zayavkalar) ---
    # Bot admin bo'lgan kanal/guruhlarga kelgan so'rovlarni avtomatik tasdiqlash
    AUTO_APPROVE_JOIN_REQUESTS: bool = os.getenv("AUTO_APPROVE_JOIN_REQUESTS", "true").lower() in ("1", "true", "yes", "ha")
    # So'rov yuborgan foydalanuvchiga yuboriladigan xabar ({name} — foydalanuvchi ismi, {chat} — kanal nomi)
    JOIN_WELCOME_TEXT: str = os.getenv(
        "JOIN_WELCOME_TEXT",
        "Assalomu alaykum, {name}! 👋\n\n"
        "✅ «{chat}» kanaliga qo'shilish so'rovingiz qabul qilindi.\n\n"
        "📥 Men Instagram, YouTube va TikTok videolarini yuklab, undagi qo'shiqni topib beraman. "
        "Qo'shiq matnidan parcha yozsangiz ham qo'shiqni topaman 🎵",
    ).replace("\\n", "\n")

    # --- Bot profilida obunachilar soni ---
    # Profildagi qisqa tavsif (nom ostida) va /start'dan oldingi tavsif; {count} — obunachilar soni
    SHOW_SUBSCRIBER_COUNT: bool = os.getenv("SHOW_SUBSCRIBER_COUNT", "true").lower() in ("1", "true", "yes", "ha")
    BOT_SHORT_DESCRIPTION: str = os.getenv(
        "BOT_SHORT_DESCRIPTION",
        "👥 {count} obunachi • 🎵 Qo'shiq va videolarni yuklab beraman",
    ).replace("\\n", "\n")
    BOT_DESCRIPTION: str = os.getenv(
        "BOT_DESCRIPTION",
        "👥 {count} obunachi\n\n"
        "🎵 Qo'shiq nomi, ijrochisi yoki matnidan parcha yozing — qo'shiqni topib beraman.\n"
        "📥 Instagram, YouTube va TikTok havolasini yuboring — videoni va undagi qo'shiqni yuklab beraman.",
    ).replace("\\n", "\n")

    ADMIN_PANEL_SECRET_KEY: str = os.getenv("ADMIN_PANEL_SECRET_KEY", "dev-secret-key")
    ADMIN_PANEL_USERNAME: str = os.getenv("ADMIN_PANEL_USERNAME", "admin")
    ADMIN_PANEL_PASSWORD: str = os.getenv("ADMIN_PANEL_PASSWORD", "admin")
    ADMIN_PANEL_HOST: str = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    ADMIN_PANEL_PORT: int = int(os.getenv("ADMIN_PANEL_PORT", "8000"))


settings = Settings()


def database_file() -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    return Path(settings.DATABASE_URL[len(prefix):]) if settings.DATABASE_URL.startswith(prefix) else None


def storage_warning() -> str | None:
    """Baza hostingda doimiy diskda bo'lmasa — ogohlantirish matni (har deployda foydalanuvchilar o'chadi)."""
    db = database_file()
    if db is None or not ON_RAILWAY:
        return None
    if PERSISTENT_DIR and str(db.resolve()).startswith(str(Path(PERSISTENT_DIR).resolve())):
        return None
    return (
        "⚠️ Ma'lumotlar bazasi doimiy diskda EMAS — har deploy/qayta ishga tushishda foydalanuvchilar "
        "ro'yxati o'chib ketadi (obunachilar soni 0 dan boshlanadi).\n\n"
        "Yechim: Railway → servis ustida o'ng tugma → Attach Volume → Mount path: /data. "
        + ("Variables'dagi DATABASE_URL'ni o'chiring yoki /data/bot_database.db ga o'zgartiring."
           if os.getenv("DATABASE_URL") else "Boshqa hech narsa sozlash shart emas.")
    )
