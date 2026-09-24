"""Claude (Anthropic) API bilan ishlash uchun yordamchi funksiyalar."""
import base64

from anthropic import AsyncAnthropic

from shared.config import settings

_client: AsyncAnthropic | None = None

SYSTEM_PROMPT = (
    "Siz Telegram botidagi foydali AI yordamchisiz. "
    "Foydalanuvchi qaysi tilda yozsa, o'sha tilda (asosan o'zbek tilida) qisqa va aniq javob bering. "
    "Javoblarni Telegram xabari uchun mos, ortiqcha uzun bo'lmagan qilib yozing."
)


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY .env faylida topilmadi. "
                "console.anthropic.com dan kalit oling va .env ga qo'shing."
            )
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def ask_text(history: list[dict]) -> str:
    """history: [{"role": "user"|"assistant", "content": "..."}]"""
    client = get_client()
    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=history,
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


async def ask_vision(image_bytes: bytes, media_type: str, question: str) -> str:
    client = get_client()
    b64 = base64.b64encode(image_bytes).decode()
    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": question or "Bu rasmda nima tasvirlangan? Batafsil tushuntiring."},
                ],
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()
