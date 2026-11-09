"""Qurilish mollari do'koni uchun AI sotuvchi bot.

Ishga tushirish (loyiha ildizidan):  python -m stroy_bot.main
"""
import asyncio
import html
import json
import logging
from datetime import datetime

import anthropic
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.chat_action import ChatActionSender

from stroy_bot.ai_agent import Customer, SalesAgent
from stroy_bot.config import BOT_DIR, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

LEADS_FILE = BOT_DIR / "leads.jsonl"
TELEGRAM_LIMIT = 4000  # Telegram 4096 belgidan uzun xabarni qabul qilmaydi

BTN_ASK = "🧱 Mahsulot so'rash"
BTN_CALC = "📐 Material hisoblash"
BTN_ORDER = "🛒 Zayavka qoldirish"
BTN_CONTACT = "📍 Manzil va aloqa"
BTN_NEW = "🔄 Yangi suhbat"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_ASK), KeyboardButton(text=BTN_CALC)],
        [KeyboardButton(text=BTN_ORDER), KeyboardButton(text=BTN_CONTACT)],
        [KeyboardButton(text=BTN_NEW)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Savolingizni yozing...",
)

# Tugma bosilganda AI ga boradigan matn (mijoz nomidan)
BUTTON_PROMPTS = {
    BTN_ASK: "Menga qurilish materiallari bo'yicha maslahat kerak.",
    BTN_CALC: "Menga material miqdorini hisoblab bering.",
    BTN_ORDER: "Zayavka qoldirmoqchiman.",
    BTN_CONTACT: "Do'koningiz qayerda joylashgan, ish vaqti va telefon raqamingiz qanday?",
}

WELCOME = (
    "Assalomu alaykum, {name}! 👋\n\n"
    "Men qurilish mollari do'konining AI sotuvchisiman. Sizga yordam beraman:\n"
    "- qaysi material nimaga mos kelishini tushuntiraman;\n"
    "- kafel, bo'yoq, sement, g'isht kabi materiallar miqdorini hisoblayman;\n"
    "- zayavkangizni qabul qilib, sotuvchimizga yetkazaman.\n\n"
    "Savolingizni oddiy qilib yozing yoki pastdagi tugmalardan foydalaning. "
    "Rasm yuborsangiz ham bo'ladi 📷"
)
ERROR_TEXT = "Kechirasiz, hozir javob bera olmadim 😔 Birozdan keyin qayta yozib ko'ring."
REFUSAL_TEXT = "Kechirasiz, bu savolga javob bera olmayman. Qurilish materiallari bo'yicha savolingiz bo'lsa, bemalol yozing."

router = Router()


def _customer(message: Message) -> Customer:
    user = message.from_user
    return Customer(id=user.id, full_name=user.full_name, username=user.username)


async def _send_long(message: Message, text: str) -> None:
    for start in range(0, len(text), TELEGRAM_LIMIT):
        await message.answer(text[start:start + TELEGRAM_LIMIT], reply_markup=MAIN_KEYBOARD)


async def _ask_agent(message: Message, agent: SalesAgent, text: str, image: bytes | None = None) -> None:
    async with ChatActionSender.typing(bot=message.bot, chat_id=message.chat.id):
        try:
            answer = await agent.reply(_customer(message), text, image)
        except anthropic.APIError:
            logger.exception("Claude API xatosi")
            await message.answer(ERROR_TEXT, reply_markup=MAIN_KEYBOARD)
            return
    await _send_long(message, answer if answer is not None else REFUSAL_TEXT)


@router.message(CommandStart())
async def cmd_start(message: Message, agent: SalesAgent) -> None:
    agent.reset(message.from_user.id)
    await message.answer(WELCOME.format(name=message.from_user.first_name), reply_markup=MAIN_KEYBOARD)


@router.message(Command("new"))
@router.message(F.text == BTN_NEW)
async def cmd_new(message: Message, agent: SalesAgent) -> None:
    agent.reset(message.from_user.id)
    await message.answer("Yangi suhbat boshlandi. Qanday yordam bera olaman?", reply_markup=MAIN_KEYBOARD)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await message.answer(f"Sizning Telegram ID raqamingiz: {message.from_user.id}")


@router.message(F.text)
async def on_text(message: Message, agent: SalesAgent) -> None:
    text = BUTTON_PROMPTS.get(message.text, message.text)
    await _ask_agent(message, agent, text)


@router.message(F.photo)
async def on_photo(message: Message, agent: SalesAgent) -> None:
    file = await message.bot.download(message.photo[-1])  # eng katta o'lcham
    await _ask_agent(message, agent, message.caption or "", image=file.read())


@router.message(F.voice | F.audio | F.video_note)
async def on_voice(message: Message) -> None:
    await message.answer(
        "Hozircha ovozli xabarlarni tinglay olmayman 🙏 Iltimos, savolingizni yozib yuboring.",
        reply_markup=MAIN_KEYBOARD,
    )


@router.message()
async def on_other(message: Message) -> None:
    await message.answer("Savolingizni matn yoki rasm ko'rinishida yuboring.", reply_markup=MAIN_KEYBOARD)


def make_lead_sender(bot: Bot):
    async def send_lead(customer: Customer, lead: dict[str, str]) -> None:
        record = {"vaqt": datetime.now().isoformat(timespec="seconds"), "telegram_id": customer.id, **lead}
        with LEADS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if not settings.ADMIN_IDS:
            raise RuntimeError("STROY_ADMIN_IDS sozlanmagan, zayavkani yuboradigan odam yo'q")

        e = html.escape
        tg = f'<a href="tg://user?id={customer.id}">{e(customer.full_name)}</a>'
        if customer.username:
            tg += f" (@{e(customer.username)})"
        text = (
            "🧾 <b>Yangi zayavka</b>\n\n"
            f"👤 Ism: {e(lead['ism'] or '—')}\n"
            f"📞 Telefon: {e(lead['telefon'])}\n"
            f"📦 Kerak: {e(lead['mahsulotlar'] or '—')}\n"
            f"📍 Manzil: {e(lead['manzil'] or '—')}\n"
            f"💬 Izoh: {e(lead['izoh'] or '—')}\n\n"
            f"Telegram: {tg}"
        )
        delivered = 0
        for admin_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
                delivered += 1
            except Exception:
                logger.exception("Admin %s ga zayavka yuborilmadi", admin_id)
        if not delivered:
            raise RuntimeError("Zayavka birorta adminga yetib bormadi")

    return send_lead


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("STROY_BOT_TOKEN topilmadi. stroy_bot/.env fayliga @BotFather tokenini yozing.")
    if not settings.ADMIN_IDS:
        logger.warning("STROY_ADMIN_IDS bo'sh: zayavkalar faqat leads.jsonl fayliga yoziladi.")

    bot = Bot(token=settings.BOT_TOKEN)
    agent = SalesAgent(lead_sender=make_lead_sender(bot))
    dp = Dispatcher(agent=agent)  # handlerlarga `agent` argumenti sifatida uzatiladi
    dp.include_router(router)

    logger.info("Qurilish mollari boti ishga tushdi (model: %s)", settings.AI_MODEL)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
