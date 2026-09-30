import asyncio

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from video_enhancer_bot.config import settings
from video_enhancer_bot.jobs import Job, JobQueue
from video_enhancer_bot.media import PRESETS

router = Router(name="enhancer")

WELCOME_TEXT = (
    "Assalomu alaykum! 👋 <b>Jonli Kadr</b> botiga xush kelibsiz 🎞\n\n"
    "🎬 Menga eski yoki sifati past videoni yuboring — men uni:\n"
    "• 🔍 yuqori aniqlikka (HD / Full HD) kattalashtiraman\n"
    "• 🧹 shovqin va \"g'ira-shira\"likdan tozalayman\n"
    "• 🌈 ranglarini yorqin va jonli qilaman\n"
    "• ✨ tafsilotlarini tiniqlashtiraman\n\n"
    "📎 Videoni oddiy video yoki fayl sifatida yuborishingiz mumkin.\n"
    "⚠️ Cheklovlar: {max_mb} MB gacha, {max_sec} soniyagacha."
)


def _welcome() -> str:
    return WELCOME_TEXT.format(
        max_mb=settings.download_limit_bytes // (1024 * 1024), max_sec=settings.MAX_DURATION_SEC
    )


def preset_keyboard(message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p.title, callback_data=f"enh:{p.key}:{message_id}")] for p in PRESETS.values()
    ])


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_start(message: Message) -> None:
    await message.answer(_welcome())


def _video_of(message: Message):
    if message.video:
        return message.video
    if message.document and (message.document.mime_type or "").startswith("video/"):
        return message.document
    if message.animation:
        return message.animation
    if message.video_note:
        return message.video_note
    return None


@router.message(F.video | F.document | F.animation | F.video_note)
async def on_video(message: Message, state: FSMContext, jobs: JobQueue) -> None:
    video = _video_of(message)
    if video is None:
        await message.answer("📎 Bu video fayl emas. Iltimos, video yuboring (mp4, mov, avi, mkv...).")
        return
    if jobs.is_busy(message.from_user.id):
        await message.answer("⏳ Oldingi videongiz hali ishlanmoqda. U tayyor bo'lgach, keyingisini yuboring.")
        return
    if video.file_size and video.file_size > settings.download_limit_bytes:
        await message.answer(
            f"❌ Video juda katta ({video.file_size // (1024 * 1024)} MB). "
            f"Eng ko'pi {settings.download_limit_bytes // (1024 * 1024)} MB.\n"
            "Videoni qisqaroq bo'laklarga bo'lib yuboring."
        )
        return
    duration = getattr(video, "duration", None)
    if duration and duration > settings.MAX_DURATION_SEC:
        await message.answer(
            f"❌ Video juda uzun ({duration} s). Eng ko'pi {settings.MAX_DURATION_SEC} soniya.\n"
            "Kerakli lavhani qirqib yuboring."
        )
        return

    # Bir nechta video ketma-ket yuborilsa ham har birining tugmasi o'z videosiga bog'lanadi
    data = await state.get_data()
    pending = data.get("pending", {})
    pending[str(message.message_id)] = video.file_id
    await state.update_data(pending=dict(list(pending.items())[-10:]))

    await message.reply("🎨 Qaysi uslubda yaxshilaymiz?", reply_markup=preset_keyboard(message.message_id))


@router.callback_query(F.data.startswith("enh:"))
async def on_preset(callback: CallbackQuery, state: FSMContext, jobs: JobQueue) -> None:
    _, preset_key, message_id = callback.data.split(":")
    data = await state.get_data()
    pending = data.get("pending", {})
    file_id = pending.pop(message_id, None)
    if file_id is None or preset_key not in PRESETS or not callback.message:
        await callback.answer("Bu video eskirgan. Iltimos, videoni qaytadan yuboring.", show_alert=True)
        return
    if jobs.is_busy(callback.from_user.id):
        await callback.answer("⏳ Oldingi videongiz hali ishlanmoqda.", show_alert=True)
        return
    await state.update_data(pending=pending)
    await callback.answer()

    status = callback.message
    await status.edit_text("🕐 Navbatga qo'yilmoqda...")
    job = Job(
        user_id=callback.from_user.id, chat_id=status.chat.id, file_id=file_id,
        reply_to_message_id=int(message_id), status_message_id=status.message_id, preset_key=preset_key,
    )
    try:
        ahead = jobs.submit(job)
    except asyncio.QueueFull:
        await status.edit_text("😔 Hozir navbat to'lib ketgan. Bir necha daqiqadan so'ng qayta yuboring.")
        return
    if ahead:
        await status.edit_text(f"🕐 Navbatdasiz: sizdan oldin {ahead} ta video bor. Tayyor bo'lganda xabar beraman.")


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("🎬 Sifatini oshirish uchun menga video yuboring.")
