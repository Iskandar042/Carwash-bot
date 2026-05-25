"""
Customer-facing flow: car owner enters their plate number and sees
queue position + wash/payment status.
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

import db
from config import WORKFLOW_LABELS, PAYMENT_LABELS
from keyboards import main_menu

# Conversation states
CUSTOMER_PLATE = 10


async def start_customer_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔍 Введите гос. номер вашего автомобиля.\n"
        "Например: <code>01 A 123 AA</code> или <code>01A123AA</code>",
        parse_mode="HTML",
    )
    return CUSTOMER_PLATE


async def receive_plate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    raw   = update.message.text.strip()
    plate = _normalize_plate(raw)

    booking = await db.get_booking_by_plate(plate)

    if not booking:
        await update.message.reply_text(
            f"❓ Активная запись для <b>{plate}</b> не найдена.\n\n"
            "Возможно, мойка уже завершена или номер введён неверно.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    queue   = await db.get_active_queue()
    pos     = db.queue_position(queue, booking["id"])
    wf      = WORKFLOW_LABELS.get(booking["workflow_status"], booking["workflow_status"])
    pay     = PAYMENT_LABELS.get(booking["payment_status"],   booking["payment_status"])
    service = booking.get("service", "—")

    if booking["workflow_status"] == "queue":
        pos_text = f"📍 Ваша позиция в очереди: <b>{pos}</b> из {len(queue)}"
    elif booking["workflow_status"] == "washing":
        pos_text = "🚿 Ваш автомобиль <b>сейчас моется</b>!"
    else:
        pos_text = "✅ Ваш автомобиль <b>готов</b>! Можете забирать."

    text = (
        f"🚗 <b>{booking['plate']}</b>\n\n"
        f"{pos_text}\n\n"
        f"Статус мойки: {wf}\n"
        f"Оплата: {pay}\n"
        f"Услуга: {service}\n"
        f"Сумма: {booking['amount']:,} сум".replace(",", " ")
    )

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_menu())
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=main_menu())
    return ConversationHandler.END


def _normalize_plate(raw: str) -> str:
    """
    Accept formats like:
      01A123AA  → 01 | A 123 AA
      01 A 123 AA
      01|A123AA
    Return canonical "NN | L NNN LL" format used in CRM.
    """
    import re
    s = raw.upper().replace("|", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Already spaced: "01 A 123 AA"
    m = re.match(r"^(\d{2})\s*([A-Z])\s*(\d{3})\s*([A-Z]{2})$", s)
    if m:
        return f"{m.group(1)} | {m.group(2)} {m.group(3)} {m.group(4)}"

    # Compact: "01A123AA"
    m = re.match(r"^(\d{2})([A-Z])(\d{3})([A-Z]{2})$", s.replace(" ", ""))
    if m:
        return f"{m.group(1)} | {m.group(2)} {m.group(3)} {m.group(4)}"

    # Return as-is and let the DB query decide
    return s


def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🚗 Проверить статус авто$"), start_customer_check)
        ],
        states={
            CUSTOMER_PLATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_plate)],
        },
        fallbacks=[MessageHandler(filters.Regex("^/cancel$"), cancel)],
        name="customer_check",
        persistent=False,
    )
