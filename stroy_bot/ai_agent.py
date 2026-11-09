"""AI sotuvchi: Claude bilan suhbat, mijoz tarixi va zayavka vositasi."""
import asyncio
import base64
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable

import anthropic

from stroy_bot.config import settings
from stroy_bot.prompts import build_system_prompt

logger = logging.getLogger(__name__)

# Server tomonidagi zaxira model (refusal bo'lsa so'rovni boshqa modelda qayta bajaradi).
# Faqat shu modellar "default" rejimini qo'llab-quvvatlaydi.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Bitta javob ichida vosita chaqiruvlari soniga chegara (cheksiz aylanib qolmasligi uchun)
_MAX_TOOL_ROUNDS = 4

LEAD_TOOL = {
    "name": "zayavka_yuborish",
    "description": (
        "Mijozning xarid so'rovini (zayavkasini) do'kon sotuvchisiga yuboradi. "
        "Mijoz telefon raqamini va nima kerakligini aytgandan keyin chaqiring. "
        "Noma'lum maydonlar uchun bo'sh qator yuboring."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "ism": {"type": "string", "description": "Mijozning ismi"},
            "telefon": {"type": "string", "description": "Mijozning telefon raqami"},
            "mahsulotlar": {
                "type": "string",
                "description": "Nima va qancha kerak, masalan: 'M400 sement 20 qop, qum 2 tonna'",
            },
            "manzil": {"type": "string", "description": "Yetkazib berish manzili (kerak bo'lsa)"},
            "izoh": {"type": "string", "description": "Qo'shimcha izoh: muddat, savollar va h.k."},
        },
        "required": ["ism", "telefon", "mahsulotlar", "manzil", "izoh"],
        "additionalProperties": False,
    },
}


@dataclass
class Customer:
    id: int
    full_name: str
    username: str | None


# (mijoz, zayavka maydonlari) -> zayavkani sotuvchiga yetkazadi
LeadSender = Callable[[Customer, dict[str, str]], Awaitable[None]]


class SalesAgent:
    def __init__(self, lead_sender: LeadSender) -> None:
        self.client = anthropic.AsyncAnthropic()
        self.lead_sender = lead_sender
        # Prompt barqaror bo'lgani uchun keshlanadi (narx va tezlik uchun foydali)
        self.system = [
            {"type": "text", "text": build_system_prompt(), "cache_control": {"type": "ephemeral"}}
        ]
        # Tarixda faqat matn saqlanadi: user/assistant juftliklari
        self.histories: dict[int, list[dict]] = defaultdict(list)
        self.locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def reset(self, user_id: int) -> None:
        self.histories.pop(user_id, None)

    async def reply(
        self, customer: Customer, text: str, image: bytes | None = None
    ) -> str | None:
        """Mijoz xabariga javob qaytaradi. None — model javob berishdan bosh tortdi."""
        # Bir mijozning xabarlari ketma-ket ishlanadi, aks holda tarix aralashib ketadi
        async with self.locks[customer.id]:
            history = self.histories[customer.id]

            content: list[dict] = []
            if image is not None:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",  # Telegram rasmlarni JPEG qilib beradi
                        "data": base64.standard_b64encode(image).decode("ascii"),
                    },
                })
            content.append({"type": "text", "text": text or "Rasmga qarab maslahat bering."})

            answer = await self._run([*history, {"role": "user", "content": content}], customer)
            if answer is None:
                return None

            history_text = f"[Mijoz rasm yubordi] {text}".strip() if image is not None else text
            history.append({"role": "user", "content": history_text})
            history.append({"role": "assistant", "content": answer})
            # Eng eski juftliklarni tashlab, tarixni chegarada ushlaymiz
            while len(history) > settings.HISTORY_LIMIT:
                del history[:2]
            return answer

    async def _run(self, messages: list[dict], customer: Customer) -> str | None:
        extra: dict = {}
        if settings.AI_MODEL in _FALLBACK_MODELS:
            extra = {"betas": [_FALLBACK_BETA], "fallbacks": "default"}

        for _ in range(_MAX_TOOL_ROUNDS + 1):
            response = await self.client.beta.messages.create(
                model=settings.AI_MODEL,
                max_tokens=16000,
                system=self.system,
                tools=[LEAD_TOOL],
                output_config={"effort": settings.AI_EFFORT},
                messages=messages,
                **extra,
            )

            if response.stop_reason == "refusal":
                logger.warning("Model javob bermadi: %s", response.stop_details)
                return None

            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            if response.stop_reason != "tool_use" or not tool_calls:
                return text or "Kechirasiz, savolingizni tushunmadim. Boshqacharoq yozib bera olasizmi?"

            messages.append({"role": "assistant", "content": response.content})
            results = [await self._execute_tool(call, customer) for call in tool_calls]
            # Barcha natijalar bitta xabarda qaytariladi
            messages.append({"role": "user", "content": results})

        logger.error("Vosita chaqiruvlari chegaradan oshdi (mijoz %s)", customer.id)
        return "Kechirasiz, so'rovingizni ishlashda muammo bo'ldi. Iltimos, qayta yozing."

    async def _execute_tool(self, call, customer: Customer) -> dict:
        result = {"type": "tool_result", "tool_use_id": call.id}
        if call.name != LEAD_TOOL["name"]:
            return {**result, "content": f"Noma'lum vosita: {call.name}", "is_error": True}

        fields = {key: str(call.input.get(key, "")).strip() for key in LEAD_TOOL["input_schema"]["properties"]}
        if not fields["telefon"]:
            return {**result, "content": "Telefon raqami yo'q. Avval mijozdan so'rang.", "is_error": True}
        try:
            await self.lead_sender(customer, fields)
        except Exception:
            logger.exception("Zayavkani yuborib bo'lmadi")
            return {
                **result,
                "content": "Zayavkani yuborib bo'lmadi. Mijozga do'konga qo'ng'iroq qilishni ayting.",
                "is_error": True,
            }
        return {**result, "content": "Zayavka sotuvchiga yuborildi."}
