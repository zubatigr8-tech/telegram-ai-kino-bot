"""Videolar navbati: ishlov berish og'ir bo'lgani uchun bir vaqtda faqat MAX_CONCURRENT_JOBS ta video
ishlanadi, qolganlari navbatda kutadi. Foydalanuvchi har bosqichda holatni ko'rib turadi."""
import asyncio
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, ReplyParameters

from video_enhancer_bot.config import settings
from video_enhancer_bot.engines import Engine
from video_enhancer_bot.media import PRESETS, MediaError, comparison_image, probe, target_size

logger = logging.getLogger(__name__)


@dataclass
class Job:
    user_id: int
    chat_id: int
    file_id: str
    reply_to_message_id: int
    status_message_id: int
    preset_key: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


def progress_bar(fraction: float, width: int = 12) -> str:
    filled = int(round(fraction * width))
    return "▰" * filled + "▱" * (width - filled) + f" {int(fraction * 100)}%"


class JobQueue:
    def __init__(self, bot: Bot, engine: Engine) -> None:
        self.bot = bot
        self.engine = engine
        self.queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=settings.MAX_QUEUE_SIZE)
        self.active_users: set[int] = set()  # navbatda yoki ishlanayotgan videosi bor foydalanuvchilar
        self._workers: list[asyncio.Task] = []

    def start(self) -> None:
        settings.WORK_DIR.mkdir(parents=True, exist_ok=True)
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(settings.MAX_CONCURRENT_JOBS)]

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    def is_busy(self, user_id: int) -> bool:
        return user_id in self.active_users

    def submit(self, job: Job) -> int:
        """Vazifani navbatga qo'shadi va undan oldin nechta video borligini qaytaradi.
        Navbat to'lgan bo'lsa asyncio.QueueFull ko'taradi."""
        ahead = self.queue.qsize()
        self.queue.put_nowait(job)
        self.active_users.add(job.user_id)
        return ahead

    async def _worker(self, n: int) -> None:
        while True:
            job = await self.queue.get()
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Vazifa %s kutilmagan xatolik bilan tugadi", job.id)
            finally:
                self.active_users.discard(job.user_id)
                self.queue.task_done()

    async def _status(self, job: Job, text: str) -> None:
        try:
            await self.bot.edit_message_text(text, chat_id=job.chat_id, message_id=job.status_message_id)
        except TelegramBadRequest:
            pass  # matn o'zgarmagan yoki xabar o'chirilgan

    async def _process(self, job: Job) -> None:
        workdir = settings.WORK_DIR / job.id
        workdir.mkdir(parents=True)
        preset = PRESETS[job.preset_key]
        try:
            await self._status(job, "⬇️ Video yuklab olinmoqda...")
            src = workdir / "input"
            await self.bot.download(job.file_id, destination=src)

            info = await probe(src)
            if info.duration > settings.MAX_DURATION_SEC:
                raise MediaError(
                    f"Video juda uzun ({int(info.duration)} s). Eng ko'pi {settings.MAX_DURATION_SEC} soniya."
                )
            w, h = target_size(info)
            header = (
                f"⚙️ Sifat oshirilmoqda — <b>{preset.title}</b>\n"
                f"📐 {info.width}×{info.height} → {w}×{h}\n\n"
            )
            await self._status(job, header + progress_bar(0))

            last_update = 0.0
            last_percent = -1

            async def on_progress(fraction: float) -> None:
                nonlocal last_update, last_percent
                percent = int(fraction * 100)
                # Telegram flood-limitiga tushmaslik uchun ko'pi bilan har 5 soniyada yangilaymiz
                if percent != last_percent and time.monotonic() - last_update >= 5:
                    last_update, last_percent = time.monotonic(), percent
                    await self._status(job, header + progress_bar(fraction))

            dst = workdir / "enhanced.mp4"
            started = time.monotonic()
            await self.engine.enhance(src, dst, info, preset, workdir, on_progress, settings.JOB_TIMEOUT_SEC)
            took = int(time.monotonic() - started)

            await self._status(job, header + progress_bar(1) + "\n\n⬆️ Yuborilmoqda...")
            compare = workdir / "compare.jpg"
            if await comparison_image(src, dst, info, compare):
                try:
                    await self.bot.send_photo(
                        job.chat_id, FSInputFile(compare),
                        caption="👈 Asl video  |  Yaxshilangan 👉" if info.height > info.width
                        else "👆 Asl video\n👇 Yaxshilangan",
                        reply_parameters=ReplyParameters(message_id=job.reply_to_message_id, allow_sending_without_reply=True),
                    )
                except TelegramBadRequest:
                    logger.warning("Solishtirma rasm yuborilmadi", exc_info=True)
            caption = f"✅ Tayyor! {info.width}×{info.height} → {w}×{h} · {preset.title}\n⏱ {took // 60} daq {took % 60} s"
            try:
                await self.bot.send_video(
                    job.chat_id, FSInputFile(dst, filename="enhanced.mp4"), caption=caption,
                    width=w, height=h, duration=int(info.duration), supports_streaming=True,
                    reply_parameters=ReplyParameters(message_id=job.reply_to_message_id, allow_sending_without_reply=True),
                )
            except TelegramBadRequest:
                # Ba'zi hollarda Telegram videoni qabul qilmaydi — fayl sifatida yuboramiz (sifat yo'qolmaydi)
                await self.bot.send_document(
                    job.chat_id, FSInputFile(dst, filename="enhanced.mp4"), caption=caption,
                    reply_parameters=ReplyParameters(message_id=job.reply_to_message_id, allow_sending_without_reply=True),
                )
            await self._delete_status(job)
        except MediaError as e:
            await self._status(job, f"❌ {e}")
        except asyncio.TimeoutError:
            await self._status(job, "❌ Ishlov berish vaqti tugadi. Qisqaroq video yuborib ko'ring.")
        except Exception:
            logger.exception("Vazifa %s xatoligi", job.id)
            await self._status(job, "❌ Kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _delete_status(self, job: Job) -> None:
        try:
            await self.bot.delete_message(job.chat_id, job.status_message_id)
        except TelegramBadRequest:
            pass
