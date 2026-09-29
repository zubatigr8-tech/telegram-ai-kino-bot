"""Ovozli ogohlantirishlar: matn → ovoz (edge-tts, bepul, kalit shart emas) → Telegram voice.

Bir xil ibora qayta-qayta generatsiya qilinmasligi uchun:
- mp3 fayl diskda saqlanadi (VOICE_CACHE_DIR);
- Telegram'ga bir marta yuklangach, uning file_id si xotirada saqlanadi va keyingi safar
  fayl qayta yuklanmaydi — ogohlantirish bir zumda yetib boradi.
Ovoz yuborib bo'lmasa (TTS serveri ishlamasa, foydalanuvchi ovozli xabarlarni taqiqlagan bo'lsa)
False qaytadi — matnli xabar baribir yuboriladi.
"""
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Awaitable, Callable

from aiogram import Bot
from aiogram.types import FSInputFile

from antiradar.config import settings

logger = logging.getLogger(__name__)

VOICES = {
    "uz": "uz-UZ-MadinaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "en": "en-US-AriaNeural",
    "tr": "tr-TR-EmelNeural",
}
# Ogohlantirish kechikmasligi uchun qisqa: 100 km/soatda 5 soniya ≈ 140 m
SYNTH_TIMEOUT_S = 5
WARMUP_TIMEOUT_S = 30


async def edge_tts_synthesize(text: str, lang: str, path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, VOICES.get(lang, VOICES["uz"])).save(str(path))


class VoiceSender:
    def __init__(
        self,
        cache_dir: Path,
        synthesize: Callable[[str, str, Path], Awaitable[None]] = edge_tts_synthesize,
    ) -> None:
        self.cache_dir = cache_dir
        self.synthesize = synthesize
        self._file_ids: dict[str, str] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @staticmethod
    def _key(lang: str, text: str) -> str:
        return hashlib.sha1(f"{lang}|{text}".encode()).hexdigest()

    async def _ensure_file(self, key: str, text: str, lang: str, timeout: float = SYNTH_TIMEOUT_S) -> Path:
        path = self.cache_dir / f"{key}.mp3"
        # Bir iborani bir vaqtda ikki foydalanuvchi uchun ikki marta generatsiya qilmaslik uchun
        async with self._locks.setdefault(key, asyncio.Lock()):
            if not path.exists() or path.stat().st_size == 0:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                await asyncio.wait_for(self.synthesize(text, lang, tmp), timeout)
                if not tmp.exists() or tmp.stat().st_size == 0:
                    raise RuntimeError("TTS bo'sh fayl qaytardi")
                tmp.replace(path)
        return path

    async def send(self, bot: Bot, chat_id: int, lang: str, text: str) -> bool:
        key = self._key(lang, text)
        try:
            file_id = self._file_ids.get(key)
            if file_id:
                await bot.send_voice(chat_id, file_id)
                return True
            path = await self._ensure_file(key, text, lang)
            message = await bot.send_voice(chat_id, FSInputFile(path, filename="alert.mp3"))
            if message.voice:
                self._file_ids[key] = message.voice.file_id
            return True
        except Exception as exc:
            logger.warning("Ovozli xabar yuborilmadi (%s): %s", lang, exc)
            return False

    async def warmup(self, phrases: list[tuple[str, str]]) -> int:
        """(til, matn) iboralarini oldindan diskka generatsiya qiladi. Tayyorlanganlar sonini qaytaradi."""
        ready = failures = 0
        for lang, text in phrases:
            try:
                await self._ensure_file(self._key(lang, text), text, lang, timeout=WARMUP_TIMEOUT_S)
                ready += 1
                failures = 0
            except Exception as exc:
                failures += 1
                logger.warning("Ovozli ibora tayyorlanmadi (%s): %s", lang, exc)
                if failures >= 3:
                    # TTS serveri umuman ishlamayapti — qolganini yo'lda kerak bo'lganda generatsiya qilamiz
                    logger.warning("Ovozli iboralarni oldindan tayyorlash to'xtatildi")
                    break
        return ready


voice_sender = VoiceSender(Path(settings.VOICE_CACHE_DIR))
