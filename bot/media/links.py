"""Xabardan Instagram / YouTube / TikTok havolasini topish va keshlash uchun normallashtirish."""
import re
from urllib.parse import parse_qs, urlsplit

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# host (www./m. olib tashlangan holda) → platforma
_PLATFORM_HOSTS = {
    "instagram.com": "instagram",
    "instagr.am": "instagram",
    "youtube.com": "youtube",
    "music.youtube.com": "youtube",
    "youtu.be": "youtube",
    "tiktok.com": "tiktok",
    "vm.tiktok.com": "tiktok",
    "vt.tiktok.com": "tiktok",
}

PLATFORM_NAMES = {"instagram": "Instagram", "youtube": "YouTube", "tiktok": "TikTok"}


def _clean_host(host: str) -> str:
    host = host.lower().split(":")[0]
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host


def detect_platform(url: str) -> str | None:
    try:
        host = _clean_host(urlsplit(url).netloc)
    except ValueError:
        return None
    return _PLATFORM_HOSTS.get(host)


def find_urls(text: str) -> list[str]:
    # Oxiridagi tinish belgilari havolaga qo'shilib qolmasin
    return [u.rstrip(".,;:!?)]}") for u in URL_RE.findall(text or "")]


def find_supported_url(text: str) -> tuple[str, str] | None:
    """Matndagi birinchi qo'llab-quvvatlanadigan havola: (url, platforma)."""
    for url in find_urls(text):
        platform = detect_platform(url)
        if platform:
            return url, platform
    return None


def normalize_url(url: str) -> str:
    """Bir xil videoga turli ko'rinishdagi havolalar (utm, igsh, si parametrlari) bitta kalit bersin."""
    parts = urlsplit(url)
    host = _clean_host(parts.netloc)
    path = parts.path.rstrip("/") or "/"

    if host == "youtu.be":
        video_id = path.strip("/").split("/")[0]
        return f"youtube:{video_id}"
    if host in ("youtube.com", "music.youtube.com"):
        if path == "/watch":
            video_id = parse_qs(parts.query).get("v", [""])[0]
            if video_id:
                return f"youtube:{video_id}"
        m = re.match(r"^/(shorts|embed|live|v)/([\w-]+)", path)
        if m:
            return f"youtube:{m.group(2)}"
    if host.endswith("instagram.com") or host == "instagr.am":
        # /reel/ID, /reels/ID, /p/ID, /tv/ID — hammasi bitta post
        m = re.search(r"/(?:reels?|p|tv)/([\w-]+)", path)
        if m:
            return f"instagram:{m.group(1)}"
    if host == "tiktok.com":
        m = re.search(r"/video/(\d+)", path)
        if m:
            return f"tiktok:{m.group(1)}"

    # Qolgan hollarda (masalan, vm.tiktok.com qisqa havolalari) — so'rov parametrlarisiz
    return f"{host}{path}"[:512]
