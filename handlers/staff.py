"""
Staff flows: login, add car (with ⬅️ Back at every step),
update wash status, update payment, view queue.

Navigation:
  ⬅️ Back    — inline button, goes to previous step in add-car flow
  ❌ Cancel  — inline button, exits the current flow
  🏠         — ReplyKeyboard fallback, exits any active conversation
"""
from telegram import Update
from telegram.ext import (
    ContextTypes, ConversationHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

import db
from lang import t, wf_label, pay_label, pay_type_label
from config import SERVICES, service_name, STAFF_PASSWORD, ADMIN_PASSWORD
from keyboards import (
    staff_menu, main_menu,
    service_keyboard, payment_type_keyboard,
    payment_status_choice_keyboard, confirm_keyboard,
    workflow_status_keyboard, payment_status_keyboard,
    car_picker_keyboard,
)
from utils import _lang, _is_staff, _SESSION_KEY

# ── Conversation states ───────────────────────────────────────────────────────
LOGIN_PASSWORD = 20
ADD_PLATE      = 21
ADD_SERVICE    = 22
ADD_PAY_TYPE   = 23
ADD_PAY_STATUS = 25   # NEW: paid now vs pay later
ADD_CONFIRM    = 24
UPD_WF_SELECT  = 30
UPD_WF_STATUS  = 31
UPD_PM_SELECT  = 40
UPD_PM_STATUS  = 41


# ── Login ─────────────────────────────────────────────────────────────────────

async def staff_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    if _is_staff(ctx):
        await update.message.reply_text(
            t("already_logged_in", lang), reply_markup=staff_menu(lang)
        )
        return ConversationHandler.END

    await update.message.reply_text(t("ask_password", lang))
    return LOGIN_PASSWORD


async def check_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang    = _lang(ctx)
    entered = update.message.text.strip()

    if entered == ADMIN_PASSWORD:
        ctx.user_data[_SESSION_KEY] = "admin"
        await update.message.reply_text(
            t("login_admin", lang), reply_markup=staff_menu(lang)
        )
        return ConversationHandler.END

    if entered == STAFF_PASSWORD:
        ctx.user_data[_SESSION_KEY] = "worker"
        await update.message.reply_text(
            t("login_worker", lang), reply_markup=staff_menu(lang)
        )
        return ConversationHandler.END

    await update.message.reply_text(t("wrong_password", lang))
    return LOGIN_PASSWORD


async def staff_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    ctx.user_data.pop(_SESSION_KEY, None)
    await update.message.reply_text(t("logged_out", lang), reply_markup=main_menu(lang))
    return ConversationHandler.END


# ── View queue ────────────────────────────────────────────────────────────────

async def view_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    if not _is_staff(ctx):
        await update.message.reply_text(t("not_logged_in", lang))
        return ConversationHandler.END

    queue = await db.get_active_queue()
    if not queue:
        await update.message.reply_text(t("queue_empty", lang), reply_markup=staff_menu(lang))
        return ConversationHandler.END

    lines = [t("queue_header", lang, count=len(queue))]
    for i, b in enumerate(queue, 1):
        wait = db.estimate_wait_minutes(queue, b["id"])
        lines.append(t(
            "queue_row", lang,
            i=i,
            plate=b["plate"],
            wf=wf_label(b.get("workflow_status", "queue"), lang),
            pay=pay_label(b.get("payment_status", "not-paid"), lang),
            wait=wait,
        ))

    await update.message.reply_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=staff_menu(lang)
    )
    return ConversationHandler.END


# ── Add car — step 1: plate ───────────────────────────────────────────────────

async def add_car_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    if not _is_staff(ctx):
        await update.message.reply_text(t("not_logged_in", lang))
        return ConversationHandler.END

    await update.message.reply_text(t("ask_plate_staff", lang), parse_mode="HTML")
    return ADD_PLATE


async def add_car_plate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.customer import normalize_plate
    lang  = _lang(ctx)
    plate = normalize_plate(update.message.text.strip())

    if not plate:
        await update.message.reply_text(
            t("plate_invalid", lang), parse_mode="HTML"
        )
        return ADD_PLATE

    ctx.user_data["new_plate"] = plate

    # Check loyalty — show greeting for returning customers
    loyalty_note = ""
    try:
        lr = await db.get_loyalty(plate)
        if lr and lr.get("visits", 0) > 0:
            loyalty_note = "\n\n" + t(
                "returning_client", lang,
                tier=lr.get("tier", "^🥉 Bronze"),
                visits=lr["visits"],
            )
    except Exception:
        pass

    await update.message.reply_text(
        t("ask_service", lang, plate=plate) + loyalty_note,
        parse_mode="HTML",
        reply_markup=service_keyboard(lang),
    )
    return ADD_SERVICE


# ── Add car — step 2: service ─────────────────────────────────────────────────

async def add_car_service(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang  = _lang(ctx)
    data  = query.data

    if data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    service_key = data.split(":", 1)[1]
    svc         = SERVICES.get(service_key, {})
    ctx.user_data["new_service"] = service_key
    price_fmt = f"{svc.get('price', 0):,}".replace(",", " ")

    await query.edit_message_text(
        t("ask_pay_type", lang,
          service=service_name(service_key, lang),
          price=price_fmt),
        parse_mode="HTML",
        reply_markup=payment_type_keyboard(lang),
    )
    return ADD_PAY_TYPE


# ── Add car — step 3: payment type ───────────────────────────────────────────

async def add_car_pay_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)
    data = query.data

    if data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    # ⬅️ Back → re-show service selection
    if data == "back":
        plate = ctx.user_data.get("new_plate", "")
        await query.edit_message_text(
            t("ask_service", lang, plate=plate),
            parse_mode="HTML",
            reply_markup=service_keyboard(lang),
        )
        return ADD_SERVICE

    pay_type = data.split(":", 1)[1]
    ctx.user_data["new_pay_type"] = pay_type

    await query.edit_message_text(
        t("ask_pay_status", lang, pay_type=pay_type_label(pay_type, lang)),
        parse_mode="HTML",
        reply_markup=payment_status_choice_keyboard(lang),
    )
    return ADD_PAY_STATUS


# ── Add car — step 4: payment status (paid now / later) ──────────────────────

async def add_car_pay_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)
    data = query.data

    if data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    # ⬅️ Back → re-show payment type selection
    if data == "back":
        svc_key   = ctx.user_data.get("new_service", "")
        svc       = SERVICES.get(svc_key, {})
        price_fmt = f"{svc.get('price', 0):,}".replace(",", " ")
        await query.edit_message_text(
            t("ask_pay_type", lang,
              service=service_name(svc_key, lang),
              price=price_fmt),
            parse_mode="HTML",
            reply_markup=payment_type_keyboard(lang),
        )
        return ADD_PAY_TYPE

    pay_status = data.split(":", 1)[1]   # "paid" or "not-paid"
    ctx.user_data["new_pay_status"] = pay_status

    plate     = ctx.user_data["new_plate"]
    svc_key   = ctx.user_data["new_service"]
    svc       = SERVICES.get(svc_key, {})
    price_fmt = f"{svc.get('price', 0):,}".replace(",", " ")
    pay_type  = ctx.user_data.get("new_pay_type", "cash")

    await query.edit_message_text(
        t("confirm_booking", lang,
          plate=plate,
          service=service_name(svc_key, lang),
          price=price_fmt,
          pay_type=pay_type_label(pay_type, lang),
          pay_status=pay_label(pay_status, lang)),
        parse_mode="HTML",
        reply_markup=confirm_keyboard(lang),
    )
    return ADD_CONFIRM


# ── Add car — step 5: confirm ─────────────────────────────────────────────────

async def add_car_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)
    data = query.data

    if data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    # ⬅️ Back → re-show payment status choice
    if data == "back":
        pay_type = ctx.user_data.get("new_pay_type", "cash")
        await query.edit_message_text(
            t("ask_pay_status", lang, pay_type=pay_type_label(pay_type, lang)),
            parse_mode="HTML",
            reply_markup=payment_status_choice_keyboard(lang),
        )
        return ADD_PAY_STATUS

    # ✅ Confirm
    plate      = ctx.user_data.pop("new_plate",      None)
    svc_key    = ctx.user_data.pop("new_service",     None)
    pay_type   = ctx.user_data.pop("new_pay_type",    "cash")
    pay_status = ctx.user_data.pop("new_pay_status",  "not-paid")

    try:
        booking_id = await db.add_booking(plate, svc_key, pay_type, pay_status)
        queue = await db.get_active_queue()
        pos   = db.queue_position(queue, booking_id)
        await query.edit_message_text(
            t("booking_saved", lang, plate=plate, pos=pos, id=booking_id),
            parse_mode="HTML",
        )
    except Exception as e:
        await query.edit_message_text(t("booking_error", lang, error=str(e)))

    return ConversationHandler.END


# ── Update wash status ────────────────────────────────────────────────────────

async def update_wf_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    if not _is_staff(ctx):
        await update.message.reply_text(t("not_logged_in", lang))
        return ConversationHandler.END

    bookings = await db.get_all_active_plates()
    if not bookings:
        await update.message.reply_text(
            t("no_active_records", lang), reply_markup=staff_menu(lang)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        t("pick_car_wf", lang),
        reply_markup=car_picker_keyboard(bookings, "wf", lang),
    )
    return UPD_WF_SELECT


async def update_wf_select_car(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)

    if query.data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    booking_id = query.data.split(":", 1)[1]
    ctx.user_data["upd_wf_id"] = booking_id

    queue   = await db.get_active_queue()
    booking = next((b for b in queue if b["id"] == booking_id), None)
    current = booking["workflow_status"] if booking else "queue"

    await query.edit_message_text(
        t("pick_wf_status", lang),
        reply_markup=workflow_status_keyboard(current, lang),
    )
    return UPD_WF_STATUS


async def update_wf_set_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)

    if query.data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    new_status = query.data.split(":", 1)[1]
    booking_id = ctx.user_data.pop("upd_wf_id", None)

    ok = await db.update_workflow_status(booking_id, new_status)
    msg = t("wf_updated", lang, status=wf_label(new_status, lang)) if ok \
          else t("wf_error", lang)
    await query.edit_message_text(msg)
    return ConversationHandler.END


# ── Update payment status ─────────────────────────────────────────────────────

async def update_pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    if not _is_staff(ctx):
        await update.message.reply_text(t("not_logged_in", lang))
        return ConversationHandler.END

    bookings = await db.get_all_active_plates()
    unpaid   = [b for b in bookings if b.get("payment_status") != "paid"]

    if not unpaid:
        await update.message.reply_text(
            t("all_paid", lang), reply_markup=staff_menu(lang)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        t("pick_car_pay", lang),
        reply_markup=car_picker_keyboard(unpaid, "pm", lang),
    )
    return UPD_PM_SELECT


async def update_pay_select_car(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)

    if query.data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    booking_id = query.data.split(":", 1)[1]
    ctx.user_data["upd_pm_id"] = booking_id

    bookings = await db.get_all_active_plates()
    booking  = next((b for b in bookings if b["id"] == booking_id), None)
    current  = booking["payment_status"] if booking else "not-paid"

    await query.edit_message_text(
        t("pick_pay_status", lang),
        reply_markup=payment_status_keyboard(current, lang),
    )
    return UPD_PM_STATUS


async def update_pay_set_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = _lang(ctx)

    if query.data == "cancel":
        await query.edit_message_text(t("cancelled", lang))
        return ConversationHandler.END

    new_status = query.data.split(":", 1)[1]
    booking_id = ctx.user_data.pop("upd_pm_id", None)

    ok  = await db.update_payment_status(booking_id, new_status)
    msg = t("pay_updated", lang, status=pay_label(new_status, lang)) if ok \
          else t("pay_error", lang)
    await query.edit_message_text(msg)
    return ConversationHandler.END


# ── Shared fallback — used when 🏠 is pressed mid-flow ───────────────────────

async def nav_fallback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    lang = _lang(ctx)
    # Clean up any temp data left in the flow
    for key in ("new_plate", "new_service", "new_pay_type", "new_pay_status",
                "upd_wf_id", "upd_pm_id"):
        ctx.user_data.pop(key, None)

    markup = staff_menu(lang) if _is_staff(ctx) else main_menu(lang)
    await update.message.reply_text(t("cancelled", lang), reply_markup=markup)
    return ConversationHandler.END


# ── Build all handlers ────────────────────────────────────────────────────────

def build_handlers() -> list:
    _fallbacks = [
        MessageHandler(filters.Regex("^🏠"), nav_fallback),
        MessageHandler(filters.COMMAND, nav_fallback),
    ]

    login_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👷"), staff_entry)],
        states={
            LOGIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, check_password),
            ],
        },
        fallbacks=_fallbacks,
        name="staff_login",
    )

    add_car_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕"), add_car_start)],
        states={
            ADD_PLATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, add_car_plate)],
            ADD_SERVICE:     [CallbackQueryHandler(add_car_service)],
            ADD_PAY_TYPE:    [CallbackQueryHandler(add_car_pay_type)],
            ADD_PAY_STATUS:  [CallbackQueryHandler(add_car_pay_status)],
            ADD_CONFIRM:     [CallbackQueryHandler(add_car_confirm)],
        },
        fallbacks=_fallbacks,
        name="add_car",
    )

    update_wf_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚙️"), update_wf_start)],
        states={
            UPD_WF_SELECT: [CallbackQueryHandler(update_wf_select_car)],
            UPD_WF_STATUS: [CallbackQueryHandler(update_wf_set_status)],
        },
        fallbacks=_fallbacks,
        name="update_workflow",
    )

    update_pay_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳"), update_pay_start)],
        states={
            UPD_PM_SELECT: [CallbackQueryHandler(update_pay_select_car)],
            UPD_PM_STATUS: [CallbackQueryHandler(update_pay_set_status)],
        },
        fallbacks=_fallbacks,
        name="update_payment",
    )

    return [login_handler, add_car_handler, update_wf_handler, update_pay_handler]
