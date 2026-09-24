from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import BTN_HOME, main_menu
from shared.db.database import get_session
from shared.db.models import User, utcnow

router = Router(name="start")


async def upsert_user(message: Message) -> None:
    async with get_session() as session:
        user = await session.get(User, message.from_user.id)
        if user is None:
            user = User(
                tg_id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
            )
            session.add(user)
        else:
            user.username = message.from_user.username
            user.full_name = message.from_user.full_name
            user.last_active = utcnow()
        await session.commit()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await upsert_user(message)
    await message.answer(
        "Assalomu alaykum! 👋\n\n"
        "Men — AI yordamchi va kino qidiruv botiman.\n\n"
        "🎬 <b>Kino qidirish</b> — kino kodini yuboring, men uni topib beraman.\n"
        "🧠 <b>AI bilan suhbat</b> — istalgan savolingizga javob beraman.\n\n"
        "Rasm yoki matnli (.txt) fayl yuborsangiz ham tahlil qilib beraman.",
        reply_markup=main_menu,
    )


@router.message(F.text == BTN_HOME)
async def go_home(message: Message, state: FSMContext) -> None:
    # Qaysi holatda (kino qidiruv/AI suhbat) bo'lishidan qat'iy nazar,
    # "Bosh menyu" tugmasi doim shu yerda ushlanadi va holatni tozalaydi.
    await state.clear()
    await message.answer("Bosh menyu 👇", reply_markup=main_menu)


@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext) -> None:
    # Bu callback SubscriptionMiddleware tomonidan qayta tekshiriladi;
    # agar shu yerga yetib kelgan bo'lsa, demak foydalanuvchi endi obuna bo'lgan.
    await callback.answer("Rahmat! Obuna tasdiqlandi ✅")
    if callback.message:
        await callback.message.answer("Endi botdan foydalanishingiz mumkin 👇", reply_markup=main_menu)
