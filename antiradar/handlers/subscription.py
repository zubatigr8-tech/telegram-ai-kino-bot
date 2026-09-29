"""Oylik obuna: Telegram Stars (⭐) orqali, har 30 kunda Telegram o'zi avtomatik yechadi."""
import datetime
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.exc import IntegrityError

from antiradar.alerts import tracker
from antiradar.config import settings
from antiradar.db import Payment, User, as_utc, get_session, utcnow
from antiradar.handlers import fmt_date
from antiradar.i18n import all_variants, t
from antiradar.keyboards import main_menu, pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name="subscription")

PAYLOAD = "sub_month"
SUBSCRIPTION_PERIOD_S = 30 * 24 * 3600  # Telegram faqat 30 kunlik davrni qabul qiladi
SUBSCRIPTION_PERIOD = datetime.timedelta(seconds=SUBSCRIPTION_PERIOD_S)


async def pay_markup(bot: Bot, lang: str):
    link = await bot.create_invoice_link(
        title=t(lang, "payment_title"),
        description=t(lang, "payment_description"),
        payload=PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label=t(lang, "payment_title"), amount=settings.PRICE_STARS)],
        subscription_period=SUBSCRIPTION_PERIOD_S,
    )
    return pay_keyboard(lang, link, settings.PRICE_STARS)


def status_text(user: User) -> str:
    now = utcnow()
    paid_until = as_utc(user.paid_until)
    trial_until = as_utc(user.trial_until)
    if paid_until and paid_until > now:
        return t(user.lang, "sub_active", date=fmt_date(paid_until))
    if trial_until and trial_until > now:
        return t(user.lang, "sub_trial", date=fmt_date(trial_until))
    return t(user.lang, "sub_none")


@router.message(Command("subscribe"))
@router.message(F.text.in_(all_variants("menu_subscription")))
async def cmd_subscription(message: Message, bot: Bot, db_user: User) -> None:
    text = status_text(db_user) + "\n\n" + t(db_user.lang, "sub_offer", price=settings.PRICE_STARS)
    await message.answer(text, reply_markup=await pay_markup(bot, db_user.lang))


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    ok = query.invoice_payload == PAYLOAD and query.currency == "XTR"
    await query.answer(ok=ok, error_message=None if ok else "Invalid invoice")


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    sp = message.successful_payment
    now = utcnow()
    async with get_session() as session:
        user = await session.get(User, message.from_user.id)
        current = as_utc(user.paid_until)
        if sp.subscription_expiration_date:
            until = datetime.datetime.fromtimestamp(sp.subscription_expiration_date, datetime.timezone.utc)
        else:
            until = max(current or now, now) + SUBSCRIPTION_PERIOD
        if current is None or until > current:
            user.paid_until = until
        session.add(
            Payment(
                tg_id=user.tg_id,
                amount=sp.total_amount,
                currency=sp.currency,
                charge_id=sp.telegram_payment_charge_id,
                is_recurring=bool(sp.is_recurring),
                paid_until=until,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # Shu to'lov allaqachon yozilgan (Telegram yangilanishni qayta yuborgan)
            await session.rollback()
            logger.warning("Takroriy to'lov xabari: %s", sp.telegram_payment_charge_id)
            return
        lang = user.lang
        paid_until = user.paid_until

    tracker.get(message.from_user.id).expired_notified = False
    await message.answer(t(lang, "payment_success", date=fmt_date(paid_until)), reply_markup=main_menu(lang))
