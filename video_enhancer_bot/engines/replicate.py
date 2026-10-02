import asyncio
import logging
import time
from pathlib import Path

import aiohttp

from video_enhancer_bot.config import settings
from video_enhancer_bot.media import (
    MediaError, Preset, ProgressCallback, VideoInfo, encode_within_limit, finish_filters, probe, target_size,
)

logger = logging.getLogger(__name__)

API = settings.REPLICATE_API_URL.rstrip("/")


class ReplicateEngine:
    """Videoni Replicate'dagi AI modelga (standart: Topaz Video Upscale) yuborib, natijani oladi,
    so'ng ffmpeg bilan rang/tiniqlik beriladi va Telegram limitiga moslab kodlanadi."""
    name = "replicate"

    async def enhance(
        self, src: Path, dst: Path, info: VideoInfo, preset: Preset, workdir: Path,
        on_progress: ProgressCallback, timeout: float,
    ) -> None:
        if not settings.REPLICATE_API_TOKEN:
            raise RuntimeError("REPLICATE_API_TOKEN .env faylida ko'rsatilmagan")
        deadline = time.monotonic() + timeout
        headers = {"Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}"}
        remote_result = workdir / "remote.mp4"

        # Standart aiohttp limiti (5 daqiqa) katta faylni yuklab olishda uzib qo'yadi — umumiy limitsiz,
        # lekin har bir o'qish uchun 2 daqiqa
        http_timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=120)
        async with aiohttp.ClientSession(headers=headers, timeout=http_timeout) as http:
            # 1) Faylni Replicate'ga yuklash
            with src.open("rb") as fh:
                form = aiohttp.FormData()
                form.add_field("content", fh, filename=src.name, content_type="video/mp4")
                async with http.post(f"{API}/files", data=form) as resp:
                    file_obj = await self._json(resp)
            await on_progress(0.05)

            # 2) Bashorat (prediction) yaratish
            payload = {"input": {settings.REPLICATE_VIDEO_FIELD: file_obj["urls"]["get"],
                                 **settings.REPLICATE_EXTRA_INPUT}}
            prediction = await self._create_prediction(http, payload)
            logger.info("Replicate prediction %s yaratildi", prediction.get("id"))

            # 3) Tayyor bo'lishini kutish. Model aniq foiz bermaydi — taxminiy progress ko'rsatamiz.
            started = time.monotonic()
            while prediction["status"] not in {"succeeded", "failed", "canceled"}:
                if time.monotonic() > deadline:
                    async with http.post(prediction["urls"]["cancel"]):
                        pass
                    raise asyncio.TimeoutError
                await asyncio.sleep(5)
                elapsed = time.monotonic() - started
                await on_progress(0.05 + 0.75 * (1 - 1 / (1 + elapsed / 120)))
                async with http.get(prediction["urls"]["get"]) as resp:
                    prediction = await self._json(resp)
            if prediction["status"] != "succeeded":
                logger.error("Replicate xatosi: %s", prediction.get("error"))
                raise MediaError("AI serverida xatolik yuz berdi. Keyinroq urinib ko'ring.")

            output = prediction["output"]
            url = output[0] if isinstance(output, list) else output
            async with http.get(url) as resp:
                resp.raise_for_status()
                with remote_result.open("wb") as f:
                    async for chunk in resp.content.iter_chunked(1 << 20):
                        f.write(chunk)
        await on_progress(0.85)

        # 4) Rang va tiniqlik. AI natijasi (masalan 4K) TARGET_HEIGHT'ga keltiriladi — aks holda
        # 1 GB xotirali serverda kodlash xotirani to'ldirib yuboradi va Telegram limitiga ham sig'maydi.
        remote_info = await probe(remote_result)
        logger.info("Replicate natijasi: %dx%d", remote_info.width, remote_info.height)
        vf = ",".join(finish_filters(preset, target_size(info), remote_info.color_matrix))
        await encode_within_limit(
            lambda enc: ["-i", str(remote_result), "-i", str(src), "-map", "0:v:0", "-map", "1:a:0?",
                         "-vf", vf, "-shortest", *enc],
            dst, info, lambda p: on_progress(0.85 + p * 0.15), deadline - time.monotonic(),
        )

    async def _create_prediction(self, http: aiohttp.ClientSession, payload: dict) -> dict:
        # "Rasmiy" modellar to'g'ridan-to'g'ri model nomi bilan chaqiriladi. Boshqalari uchun
        # API 404 qaytaradi — unda modelning oxirgi versiyasini olib, versiya orqali chaqiramiz.
        async with http.post(f"{API}/models/{settings.REPLICATE_MODEL}/predictions", json=payload) as resp:
            if resp.status != 404:
                return await self._json(resp)
        async with http.get(f"{API}/models/{settings.REPLICATE_MODEL}") as resp:
            model = await self._json(resp)
        version = (model.get("latest_version") or {}).get("id")
        if not version:
            logger.error("Replicate modeli %s uchun versiya topilmadi", settings.REPLICATE_MODEL)
            raise MediaError("AI modeli topilmadi.")
        async with http.post(f"{API}/predictions", json={"version": version, **payload}) as resp:
            return await self._json(resp)

    @staticmethod
    async def _json(resp: aiohttp.ClientResponse) -> dict:
        if resp.status >= 400:
            logger.error("Replicate API %s: %s", resp.status, await resp.text())
            raise MediaError("AI serveriga ulanib bo'lmadi.")
        return await resp.json()
