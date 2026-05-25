"""All Telegram keyboards used by the bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import SERVICES, WORKFLOW_LABELS, PAYMENT_LABELS


# ── Main menus ───────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🚗 Проверить статус авто"],
            ["👷 Вход для персонала"],
        ],
        resize_keyboard=True,
    )


def staff_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["➕ Принять авто"],
            ["🔄 Обновить статус мойки"],
            ["💳 Отметить оплату"],
            ["📋 Текущая очередь"],
            ["🚪 Выйти"],
        ],
        resize_keyboard=True,
    )


# ── Service selection ─────────────────────────────────────────────────────────

def service_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            f"{s['name']} — {s['price']:,} сум ({s['dur']} мин)".replace(",", " "),
            callback_data=f"svc:{key}"
        )]
        for key, s in SERVICES.items()
    ]
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Payment type ──────────────────────────────────────────────────────────────

def payment_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 Наличные", callback_data="pay_type:cash"),
            InlineKeyboardButton("💳 Карта",    callback_data="pay_type:card"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])


# ── Confirm booking ───────────────────────────────────────────────────────────

def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm"),
            InlineKeyboardButton("✏️ Изменить",    callback_data="edit"),
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ])


# ── Workflow status picker ────────────────────────────────────────────────────

def workflow_status_keyboard(current: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, label in WORKFLOW_LABELS.items():
        marker = " ◀" if key == current else ""
        buttons.append([InlineKeyboardButton(label + marker, callback_data=f"wf:{key}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Payment status picker ─────────────────────────────────────────────────────

def payment_status_keyboard(current: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, label in PAYMENT_LABELS.items():
        marker = " ◀" if key == current else ""
        buttons.append([InlineKeyboardButton(label + marker, callback_data=f"ps:{key}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Car picker (from active queue) ───────────────────────────────────────────

def car_picker_keyboard(bookings: list[dict], action_prefix: str) -> InlineKeyboardMarkup:
    """
    action_prefix: "wf" (workflow) or "pm" (payment)
    callback_data format: "{action_prefix}_car:{booking_id}"
    """
    buttons = []
    for b in bookings:
        wf  = WORKFLOW_LABELS.get(b.get("workflow_status", ""), "?")
        pay = PAYMENT_LABELS.get(b.get("payment_status", ""), "?")
        label = f"{b['plate']}  {wf} / {pay}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{action_prefix}_car:{b['id']}")])
    buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)
