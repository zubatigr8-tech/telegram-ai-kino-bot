from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.claude_client import ask_text
from bot.keyboards import BTN_AI, in_mode_menu
from bot.states import UserFlow

router = Router(name="ai_chat")

MAX_HISTORY_MESSAGES = 12  # oxirgi N ta xabar (user+assistant jami) kontekst uchun saqlanadi


@router.message(F.text == BTN_AI)
async def start_ai_chat(message: Message, state: FSMContext) -> None:
    await state.set_state(UserFlow.ai_chat)
    await state.update_data(history=[])
    await message.answer(
        "🧠 AI suhbat rejimi yoqildi. Savolingizni yozing.\n\n"
        "Bosh menyuga qaytish uchun pastdagi tugmani bosing.",
        reply_markup=in_mode_menu,
    )


@router.message(UserFlow.ai_chat, F.text)
async def handle_ai_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    history = data.get("history", [])
    history.append({"role": "user", "content": message.text})

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        reply = await ask_text(history[-MAX_HISTORY_MESSAGES:])
    except RuntimeError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    except Exception:
        await message.answer("⚠️ AI bilan bog'lanishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
        return

    history.append({"role": "assistant", "content": reply})
    await state.update_data(history=history[-MAX_HISTORY_MESSAGES:])
    await message.answer(reply)
