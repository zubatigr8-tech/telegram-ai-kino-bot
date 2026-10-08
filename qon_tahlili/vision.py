"""Laboratoriya blankasining rasmidan ko'rsatkichlarni o'qish (Claude orqali, ixtiyoriy).

ANTHROPIC_API_KEY o'rnatilmagan bo'lsa, bu funksiya o'chiq bo'ladi va foydalanuvchidan
natijalarni matn ko'rinishida yozish so'raladi. Rasmdan faqat raqamlar o'qiladi —
baholash va xulosalar baribir analyzer.py dagi qoidalar bilan qilinadi.
"""
import base64
import json
import logging
import os

import anthropic

from qon_tahlili.markers import MARKERS

logger = logging.getLogger(__name__)

MODEL = os.getenv("QON_VISION_MODEL", "claude-opus-5-5")

_SCHEMA = {
    "type": "object",
    "properties": {
        "values": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": [m.key for m in MARKERS]},
                    "value": {"type": "number"},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["values"],
    "additionalProperties": False,
}

_MARKER_LIST = "\n".join(f"- {m.key}: {m.name} [{m.unit}] ({', '.join(m.aliases[:4])})" for m in MARKERS)

_PROMPT = f"""This image is a blood test result sheet (likely in Uzbek, Russian or English).
Extract the patient's measured value for every analyte below that appears on the sheet.

Analytes (key: name [target unit] (common names)):
{_MARKER_LIST}

Rules:
- Use the patient's result, never the reference range column.
- If the sheet uses a different unit than the target unit, convert to the target unit.
- Leukocyte differential (neut, lymph, mono, eos) must be in percent.
- Skip anything you cannot read with confidence, and analytes not in the list."""


class VisionUnavailable(Exception):
    pass


def is_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


async def extract_from_image(image: bytes, media_type: str = "image/jpeg") -> dict[str, float]:
    if not is_enabled():
        raise VisionUnavailable("ANTHROPIC_API_KEY o'rnatilmagan")

    client = anthropic.AsyncAnthropic()
    try:
        response = await client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            # Xavfsizlik filtri so'rovni rad etsa, server tavsiya etilgan boshqa modelda qayta urinadi
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": media_type,
                        "data": base64.standard_b64encode(image).decode(),
                    }},
                    {"type": "text", "text": _PROMPT},
                ],
            }],
        )
    except anthropic.RateLimitError as e:
        raise VisionUnavailable("Juda ko'p so'rov, birozdan keyin urinib ko'ring") from e
    except anthropic.APIStatusError as e:
        logger.error("Claude API xatosi %s: %s", e.status_code, e.message)
        raise VisionUnavailable("Rasmni o'qish xizmatida xatolik") from e
    except anthropic.APIConnectionError as e:
        raise VisionUnavailable("Rasmni o'qish xizmatiga ulanib bo'lmadi") from e

    if response.stop_reason != "end_turn":
        logger.warning("Rasm o'qilmadi, stop_reason=%s", response.stop_reason)
        raise VisionUnavailable("Rasmni o'qib bo'lmadi")

    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    return {item["key"]: item["value"] for item in data["values"]}
