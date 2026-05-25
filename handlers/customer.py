"""
Customer flow: car owner enters their plate number and sees
queue position, estimated wait time, and payment status.
"""
import re
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

import db
from lang import t, wf_label, pay_label
from config import service_name
from keyboards import main_menu

# ── State ─────────────────────────────────────────────────────────────────────
CUSTOMER_PLATE = 10


def _lang(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("lang", "ru")


# ── Entry ─────────────────────────────────────────────────────────────────────

async def start_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    await update.message.reply_text(t("ask_plate", lang), parse_mode="HTML")
    return CUSTOMER_PLATE


# ── Plate input ───────────────────────────────────────────────────────────────

async def receive_plate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang  = _lang(ctx)
    raw   = update.message.text.strip()
    plate = normalize_plate(raw)

    if not plate:
        await update.message.reply_text(
            t("plate_invalid", lang), parse_mode="HTML"
        )
        return CUSTOMER_PLATE   # stay in same state, ask again

    booking = await db.get_booking_by_plate(plate)

    if not booking:
        await update.message.reply_text(
            t("plate_not_found", lang, plate=plate),
            parse_mode="HTML",
            reply_markup=main_menu(lang),
        )
        return ConversationHandler.END

    queue  = await db.get_active_queue()
    pos    = db.queue_position(queue, booking["id"])
    wait   = db.estimate_wait_minutes(queue, booking["id"])
    wf     = wf_label(booking.get("workflow_status", "queue"), lang)
    pay    = pay_label(booking.get("payment_status",  "not-paid"), lang)
    svc    = service_name(booking.get("service", ""), lang)

    wf_status = booking.get("workflow_status", "queue")
    if wf_status == "queue":
        pos_text = t("status_in_queue", lang, pos=pos, total=len(queue), wait=wait)
    elif wf_status == "washing":
        pos_text = t("status_washing", lang)
    else:
        pos_text = t("status_done", lang)

    amount_fmt = f"{booking.get('amount', 0):,}".replace(",", " ")

    text = t(
        "status_card", lang,
        plate=booking["plate"],
        pos_text=pos_text,
        wf=wf, pay=pay,
        service=svc,
        amount=amount_fmt,
    )

    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=main_menu(lang)
    )
    return ConversationHandler.END


# ── Fallback ──────────────────────────────────────────────────────────────────

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    await update.message.reply_text(t("cancelled", lang), reply_markup=main_menu(lang))
    return ConversationHandler.END


# ── Plate normaliser ──────────────────────────────────────────────────────────

def normalize_plate(raw: str) -> str:
    """
    Accept formats:
      01A123AA  →  01 | A 123 AA
      01 A 123 AA
      01|A 123 AA
    Returns canonical "NN | L NNN LL" or empty string if unrecognisable.
    """
    s = raw.upper().replace("|", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Already spaced: "01 A 123 AA"
    m = re.match(r"^(\d{2})\s+([A-Z])\s+(\d{3})\s+([A-Z]{2})$", s)
    if m:
        return f"{m.group(1)} | {m.group(2)} {m.group(3)} {m.group(4)}"

    # Compact (no spaces): "01A123AA"
    m = re.match(r"^(\d{2})([A-Z])(\d{3})([A-Z]{2})$", s.replace(" ", ""))
    if m:
        return f"{m.group(1)} | {m.group(2)} {m.group(3)} {m.group(4)}"

    # Partial match — return as-is and let DB decide
    if len(s) >= 6:
        return s

    return ""   # too short — signal invalid


# ── Register handler ──────────────────────────────────────────────────────────

def build_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("🚗"), start_check),
        ],
        states={
            CUSTOMER_PLATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_plate),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("🏠"), cancel),
            MessageHandler(filters.COMMAND, cancel),
        ],
        name="customer_check",
        persistent=False,
    )
