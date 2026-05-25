"""
All Telegram keyboards.
Every public function accepts `lang` (default "ru") and returns the
appropriate keyboard with translated labels.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from config import SERVICES, service_name
from lang import t, wf_label, pay_label


# ── Language picker (inline, shown at /start and /lang) ──────────────────────

def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский",    callback_data="lang:ru"),
        InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz"),
    ]])


# ── Main menus (ReplyKeyboard) ────────────────────────────────────────────────

def main_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Menu for non-staff users (customer-facing)."""
    return ReplyKeyboardMarkup(
        [
            [t("btn_check_status", lang)],
            [t("btn_staff_login",  lang)],
            [t("btn_change_lang",  lang)],
        ],
        resize_keyboard=True,
    )


def staff_menu(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Menu shown after staff login."""
    return ReplyKeyboardMarkup(
        [
            [t("btn_add_car",      lang)],
            [t("btn_update_wash",  lang), t("btn_mark_payment", lang)],
            [t("btn_view_queue",   lang)],
            [t("btn_main_menu",    lang), t("btn_restart",      lang)],
            [t("btn_logout",       lang)],
        ],
        resize_keyboard=True,
    )


# ── Service selection (inline) ────────────────────────────────────────────────

def service_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    unit = "сум" if lang == "ru" else "so'm"
    min_ = "мин" if lang == "ru" else "daq"
    rows = [
        [InlineKeyboardButton(
            f"{service_name(key, lang)} — {svc['price']:,} {unit} ({svc['dur']} {min_})".replace(",", " "),
            callback_data=f"svc:{key}",
        )]
        for key, svc in SERVICES.items()
    ]
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(rows)


# ── Payment type (inline) ─────────────────────────────────────────────────────

def payment_type_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t("btn_cash", lang), callback_data="pay_type:cash"),
            InlineKeyboardButton(t("btn_card", lang), callback_data="pay_type:card"),
        ],
        [
            InlineKeyboardButton(t("btn_back",   lang), callback_data="back"),
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="cancel"),
        ],
    ])


# ── Confirm booking (inline) ──────────────────────────────────────────────────

def confirm_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_confirm", lang), callback_data="confirm")],
        [
            InlineKeyboardButton(t("btn_back",   lang), callback_data="back"),
            InlineKeyboardButton(t("btn_cancel", lang), callback_data="cancel"),
        ],
    ])


# ── Workflow status picker (inline) ──────────────────────────────────────────

def workflow_status_keyboard(current: str, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    for key in ("queue", "washing", "done"):
        label  = wf_label(key, lang)
        marker = "  ◀" if key == current else ""
        rows.append([InlineKeyboardButton(label + marker, callback_data=f"wf:{key}")])
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(rows)


# ── Payment status picker (inline) ───────────────────────────────────────────

def payment_status_keyboard(current: str, lang: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    for key in ("not-paid", "pending", "paid"):
        label  = pay_label(key, lang)
        marker = "  ◀" if key == current else ""
        rows.append([InlineKeyboardButton(label + marker, callback_data=f"ps:{key}")])
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(rows)


# ── Car picker (inline) ───────────────────────────────────────────────────────

def car_picker_keyboard(
    bookings: list[dict],
    action_prefix: str,        # "wf" or "pm"
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """
    One button per active booking.
    callback_data: "{action_prefix}_car:{booking_id}"
    """
    rows = []
    for b in bookings:
        wf  = wf_label(b.get("workflow_status", "queue"), lang)
        pay = pay_label(b.get("payment_status",  "not-paid"), lang)
        rows.append([InlineKeyboardButton(
            f"{b['plate']}  {wf} · {pay}",
            callback_data=f"{action_prefix}_car:{b['id']}",
        )])
    rows.append(_cancel_row(lang))
    return InlineKeyboardMarkup(rows)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _cancel_row(lang: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(t("btn_cancel", lang), callback_data="cancel")]
