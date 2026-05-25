"""
Staff-facing flows (worker / manager):
  1. Login with password
  2. Add new car to queue
  3. Update wash status (queue → washing → done)
  4. Update payment status
  5. View current queue
"""
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import db
from config import SERVICES, WORKFLOW_LABELS, PAYMENT_LABELS, STAFF_PASSWORD, ADMIN_PASSWORD
from keyboards import (
    staff_menu, main_menu,
    service_keyboard, payment_type_keyboard, confirm_keyboard,
    workflow_status_keyboard, payment_status_keyboard,
    car_picker_keyboard,
)

# ── Conversation states ───────────────────────────────────────────────────────
LOGIN_PASSWORD   = 20
ADD_PLATE        = 21
ADD_SERVICE      = 22
ADD_PAY_TYPE     = 23
ADD_CONFIRM      = 24
UPD_WF_SELECT    = 30
UPD_WF_STATUS    = 31
UPD_PM_SELECT    = 40
UPD_PM_STATUS    = 41

SESSION_KEY = "staff_role"  # stored in user_data


def _is_staff(ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    return ctx.user_data.get(SESSION_KEY) in ("worker", "admin")


# ── Login ─────────────────────────────────────────────────────────────────────

async def staff_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_staff(ctx):
        await update.message.reply_text("Вы уже вошли как персонал.", reply_markup=staff_menu())
        return ConversationHandler.END

    await update.message.reply_text(
        "🔐 Введите пароль для входа как сотрудник:"
    )
    return LOGIN_PASSWORD


async def check_password(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    entered = update.message.text.strip()
    if entered == ADMIN_PASSWORD:
        ctx.user_data[SESSION_KEY] = "admin"
        await update.message.reply_text("✅ Добро пожаловать, Администратор!", reply_markup=staff_menu())
        return ConversationHandler.END
    if entered == STAFF_PASSWORD:
        ctx.user_data[SESSION_KEY] = "worker"
        await update.message.reply_text("✅ Добро пожаловать, Сотрудник!", reply_markup=staff_menu())
        return ConversationHandler.END

    await update.message.reply_text("❌ Неверный пароль. Попробуйте ещё раз:")
    return LOGIN_PASSWORD


async def staff_logout(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data.pop(SESSION_KEY, None)
    await update.message.reply_text("Вы вышли из системы.", reply_markup=main_menu())
    return ConversationHandler.END


# ── View queue ────────────────────────────────────────────────────────────────

async def view_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_staff(ctx):
        await update.message.reply_text("Сначала войдите как сотрудник.")
        return ConversationHandler.END

    queue = await db.get_active_queue()
    if not queue:
        await update.message.reply_text("Очередь пуста.", reply_markup=staff_menu())
        return ConversationHandler.END

    lines = ["📋 <b>Текущая очередь</b>\n"]
    for i, b in enumerate(queue, 1):
        wf  = WORKFLOW_LABELS.get(b["workflow_status"], "?")
        pay = PAYMENT_LABELS.get(b["payment_status"],   "?")
        lines.append(f"{i}. <b>{b['plate']}</b>  {wf} / {pay}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=staff_menu())
    return ConversationHandler.END


# ── Add car ───────────────────────────────────────────────────────────────────

async def add_car_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_staff(ctx):
        await update.message.reply_text("Сначала войдите как сотрудник.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🚗 Введите гос. номер автомобиля.\nПример: <code>01 A 123 AA</code>",
        parse_mode="HTML",
    )
    return ADD_PLATE


async def add_car_plate(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.customer import _normalize_plate
    plate = _normalize_plate(update.message.text.strip())
    ctx.user_data["new_plate"] = plate

    await update.message.reply_text(
        f"Номер: <b>{plate}</b>\n\nВыберите услугу:",
        parse_mode="HTML",
        reply_markup=service_keyboard(),
    )
    return ADD_SERVICE


async def add_car_service(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    service_key = data.split(":", 1)[1]
    svc = SERVICES.get(service_key, {})
    ctx.user_data["new_service"] = service_key

    await query.edit_message_text(
        f"Услуга: <b>{svc.get('name', service_key)}</b> — {svc.get('price', 0):,} сум\n\n"
        f"Выберите способ оплаты:".replace(",", " "),
        parse_mode="HTML",
        reply_markup=payment_type_keyboard(),
    )
    return ADD_PAY_TYPE


async def add_car_pay_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    pay_type = query.data.split(":", 1)[1]
    ctx.user_data["new_pay_type"] = pay_type
    pay_label = "Наличные" if pay_type == "cash" else "Карта"

    plate    = ctx.user_data["new_plate"]
    svc_key  = ctx.user_data["new_service"]
    svc      = SERVICES.get(svc_key, {})

    summary = (
        f"📋 <b>Подтвердите запись</b>\n\n"
        f"Номер: <b>{plate}</b>\n"
        f"Услуга: {svc.get('name', svc_key)}\n"
        f"Сумма: {svc.get('price', 0):,} сум\n"
        f"Оплата: {pay_label}".replace(",", " ")
    )
    await query.edit_message_text(summary, parse_mode="HTML", reply_markup=confirm_keyboard())
    return ADD_CONFIRM


async def add_car_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data in ("cancel", "edit"):
        await query.edit_message_text("Отменено. Начните заново через меню.")
        return ConversationHandler.END

    plate    = ctx.user_data.pop("new_plate")
    svc_key  = ctx.user_data.pop("new_service")
    pay_type = ctx.user_data.pop("new_pay_type")

    try:
        booking_id = await db.add_booking(plate, svc_key, pay_type)
        queue = await db.get_active_queue()
        pos   = db.queue_position(queue, booking_id)
        await query.edit_message_text(
            f"✅ Автомобиль <b>{plate}</b> добавлен в очередь.\n"
            f"Позиция в очереди: <b>{pos}</b>\n"
            f"ID записи: <code>{booking_id}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка при сохранении: {e}")

    return ConversationHandler.END


# ── Update wash status ────────────────────────────────────────────────────────

async def update_wf_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_staff(ctx):
        await update.message.reply_text("Сначала войдите как сотрудник.")
        return ConversationHandler.END

    bookings = await db.get_all_active_plates()
    if not bookings:
        await update.message.reply_text("Нет активных записей.", reply_markup=staff_menu())
        return ConversationHandler.END

    await update.message.reply_text(
        "Выберите автомобиль:",
        reply_markup=car_picker_keyboard(bookings, "wf"),
    )
    return UPD_WF_SELECT


async def update_wf_select_car(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    booking_id = query.data.split(":", 1)[1]
    ctx.user_data["upd_wf_id"] = booking_id

    # Fetch current status
    queue   = await db.get_active_queue()
    booking = next((b for b in queue if b["id"] == booking_id), None)
    current = booking["workflow_status"] if booking else "queue"

    await query.edit_message_text(
        "Выберите новый статус мойки:",
        reply_markup=workflow_status_keyboard(current),
    )
    return UPD_WF_STATUS


async def update_wf_set_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    new_status = query.data.split(":", 1)[1]
    booking_id = ctx.user_data.pop("upd_wf_id", None)

    ok = await db.update_workflow_status(booking_id, new_status)
    label = WORKFLOW_LABELS.get(new_status, new_status)

    if ok:
        await query.edit_message_text(f"✅ Статус обновлён: {label}")
    else:
        await query.edit_message_text("❌ Не удалось обновить статус.")

    return ConversationHandler.END


# ── Update payment status ─────────────────────────────────────────────────────

async def update_pay_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    if not _is_staff(ctx):
        await update.message.reply_text("Сначала войдите как сотрудник.")
        return ConversationHandler.END

    bookings = await db.get_all_active_plates()
    unpaid   = [b for b in bookings if b.get("payment_status") != "paid"]

    if not unpaid:
        await update.message.reply_text("Все активные записи уже оплачены.", reply_markup=staff_menu())
        return ConversationHandler.END

    await update.message.reply_text(
        "Выберите автомобиль:",
        reply_markup=car_picker_keyboard(unpaid, "pm"),
    )
    return UPD_PM_SELECT


async def update_pay_select_car(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    booking_id = query.data.split(":", 1)[1]
    ctx.user_data["upd_pm_id"] = booking_id

    bookings = await db.get_all_active_plates()
    booking  = next((b for b in bookings if b["id"] == booking_id), None)
    current  = booking["payment_status"] if booking else "not-paid"

    await query.edit_message_text(
        "Выберите статус оплаты:",
        reply_markup=payment_status_keyboard(current),
    )
    return UPD_PM_STATUS


async def update_pay_set_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("Отменено.")
        return ConversationHandler.END

    new_status = query.data.split(":", 1)[1]
    booking_id = ctx.user_data.pop("upd_pm_id", None)

    ok = await db.update_payment_status(booking_id, new_status)
    label = PAYMENT_LABELS.get(new_status, new_status)

    if ok:
        await query.edit_message_text(f"✅ Оплата обновлена: {label}")
    else:
        await query.edit_message_text("❌ Не удалось обновить оплату.")

    return ConversationHandler.END


# ── Generic cancel ────────────────────────────────────────────────────────────

async def cancel_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.", reply_markup=staff_menu())
    return ConversationHandler.END


# ── Build all ConversationHandlers ────────────────────────────────────────────

def build_handlers() -> list:
    login_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👷 Вход для персонала$"), staff_entry)],
        states={
            LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_password)],
        },
        fallbacks=[MessageHandler(filters.Regex("^/cancel$"), cancel_handler)],
        name="staff_login",
    )

    add_car_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Принять авто$"), add_car_start)],
        states={
            ADD_PLATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_car_plate)],
            ADD_SERVICE: [CallbackQueryHandler(add_car_service)],
            ADD_PAY_TYPE:[CallbackQueryHandler(add_car_pay_type)],
            ADD_CONFIRM: [CallbackQueryHandler(add_car_confirm)],
        },
        fallbacks=[MessageHandler(filters.Regex("^/cancel$"), cancel_handler)],
        name="add_car",
    )

    update_wf_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔄 Обновить статус мойки$"), update_wf_start)],
        states={
            UPD_WF_SELECT: [CallbackQueryHandler(update_wf_select_car)],
            UPD_WF_STATUS: [CallbackQueryHandler(update_wf_set_status)],
        },
        fallbacks=[MessageHandler(filters.Regex("^/cancel$"), cancel_handler)],
        name="update_workflow",
    )

    update_pay_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 Отметить оплату$"), update_pay_start)],
        states={
            UPD_PM_SELECT: [CallbackQueryHandler(update_pay_select_car)],
            UPD_PM_STATUS: [CallbackQueryHandler(update_pay_set_status)],
        },
        fallbacks=[MessageHandler(filters.Regex("^/cancel$"), cancel_handler)],
        name="update_payment",
    )

    return [login_handler, add_car_handler, update_wf_handler, update_pay_handler]
